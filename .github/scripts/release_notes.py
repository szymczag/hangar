#!/usr/bin/env python3

# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validate curated release notes and assemble deterministic Hangar release notes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence

from release_metadata import (
    MetadataError,
    UpstreamBase,
    load_upstream_base,
    parse_release_tag,
    parse_upstream_base,
    validate_commit_sha,
    validate_upstream_ancestry,
)


HANGAR_REPOSITORY = "https://github.com/szymczag/hangar"
IMAGE_PREFIX = "ghcr.io/szymczag/hangar-"
IMAGE_NAMES = ("web", "admin", "space", "live", "api", "proxy", "aio")
REQUIRED_CURATED_SECTIONS = (
    "Security and privacy",
    "Migrations and compatibility",
    "Known limitations and rollback",
)
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class UpstreamTransitionReview:
    release_tag: str
    previous_release_tag: str
    repository: str
    previous_revision: str
    current_revision: str
    rationale: str


@dataclass(frozen=True)
class ResolvedUpstreamTransition:
    current_commit: str
    current_upstream: UpstreamBase
    previous_tag: str | None
    previous_commit: str | None
    previous_upstream: UpstreamBase | None
    review: UpstreamTransitionReview | None
    is_linear: bool


def _run_git(repository_root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )


def load_curated_notes(notes_directory: Path, git_tag: str) -> str:
    parse_release_tag(git_tag)
    notes_path = notes_directory / f"{git_tag}.md"
    try:
        content = notes_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise MetadataError(f"missing curated release notes: {notes_path}") from exc

    lines = content.splitlines()
    expected_headings = [f"## {section}" for section in REQUIRED_CURATED_SECTIONS]
    actual_headings = [(index, line) for index, line in enumerate(lines) if line.startswith("#")]
    if [heading for _, heading in actual_headings] != expected_headings:
        raise MetadataError("curated release notes must contain only the required headings in order")

    for index, (start, heading) in enumerate(actual_headings):
        body_start = start + 1
        body_end = actual_headings[index + 1][0] if index + 1 < len(actual_headings) else len(lines)
        body = "\n".join(lines[body_start:body_end]).strip()
        if not body:
            raise MetadataError(f"curated release-note section is empty: {heading}")

    return content


def _flatten_release_pages(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        releases = []
        for item in value:
            releases.extend(_flatten_release_pages(item))
        return releases
    raise MetadataError("GitHub release data must contain only JSON arrays and objects")


def select_previous_release(release_pages: Any, current_tag: str) -> str | None:
    parse_release_tag(current_tag)
    candidates: list[tuple[datetime, str]] = []
    seen_tags = set()

    for release in _flatten_release_pages(release_pages):
        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str):
            raise MetadataError("GitHub release data contains a non-string tag name")
        if not tag_name.startswith("hangar-"):
            continue
        try:
            parse_release_tag(tag_name)
        except MetadataError as exc:
            raise MetadataError(f"published release uses an invalid Hangar tag: {tag_name}") from exc
        if tag_name == current_tag:
            continue
        if release.get("draft") is True:
            continue
        if release.get("draft") is not False:
            raise MetadataError(f"published release has an invalid draft state: {tag_name}")
        if tag_name in seen_tags:
            raise MetadataError(f"GitHub release data contains a duplicate tag: {tag_name}")
        seen_tags.add(tag_name)

        published_at = release.get("published_at")
        if not isinstance(published_at, str):
            raise MetadataError(f"published release is missing its publication date: {tag_name}")
        try:
            publication_time = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MetadataError(f"published release has an invalid publication date: {tag_name}") from exc
        if publication_time.tzinfo is None:
            raise MetadataError(f"published release date must include a timezone: {tag_name}")
        candidates.append((publication_time, tag_name))

    return max(candidates)[1] if candidates else None


def load_digests(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MetadataError(f"cannot read release digests: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MetadataError("release digests must be valid JSON") from exc
    if not isinstance(data, dict) or set(data) != set(IMAGE_NAMES):
        raise MetadataError("release digests must contain exactly the seven Hangar image names")
    if not all(isinstance(value, str) and _DIGEST_PATTERN.fullmatch(value) for value in data.values()):
        raise MetadataError("release digests contain an invalid OCI digest")
    return {image: data[image] for image in IMAGE_NAMES}


def load_upstream_transition_reviews(path: Path) -> dict[str, UpstreamTransitionReview]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MetadataError(f"cannot read upstream transition reviews: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MetadataError("upstream transition reviews must be valid JSON") from exc

    if not isinstance(data, dict) or set(data) != {"schema_version", "reviews"}:
        raise MetadataError("upstream transition reviews must use the exact schema")
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise MetadataError("unsupported upstream transition review schema version")
    if not isinstance(data["reviews"], list) or len(data["reviews"]) > 100:
        raise MetadataError("upstream transition reviews must contain at most 100 entries")

    expected_keys = {
        "release_tag",
        "previous_release_tag",
        "repository",
        "previous_revision",
        "current_revision",
        "rationale",
    }
    reviews: dict[str, UpstreamTransitionReview] = {}
    for entry in data["reviews"]:
        if not isinstance(entry, dict) or set(entry) != expected_keys:
            raise MetadataError("upstream transition review entry must use the exact schema")
        if not all(isinstance(entry[key], str) for key in expected_keys):
            raise MetadataError("upstream transition review fields must be strings")

        release_tag = entry["release_tag"]
        previous_release_tag = entry["previous_release_tag"]
        parse_release_tag(release_tag)
        parse_release_tag(previous_release_tag)
        if release_tag == previous_release_tag:
            raise MetadataError("reviewed release tags must differ")
        repository = entry["repository"]
        if repository != "https://github.com/makeplane/plane":
            raise MetadataError("upstream transition review uses an unapproved repository")
        previous_revision = validate_commit_sha(
            entry["previous_revision"], field_name="reviewed previous upstream revision"
        )
        current_revision = validate_commit_sha(
            entry["current_revision"], field_name="reviewed current upstream revision"
        )
        if previous_revision == current_revision:
            raise MetadataError("reviewed upstream revisions must differ")
        rationale = entry["rationale"].strip()
        if (
            not 20 <= len(rationale) <= 500
            or len(rationale.splitlines()) != 1
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in rationale)
        ):
            raise MetadataError("upstream transition review rationale must be a single safe line")
        if release_tag in reviews:
            raise MetadataError(f"duplicate upstream transition review: {release_tag}")

        reviews[release_tag] = UpstreamTransitionReview(
            release_tag=release_tag,
            previous_release_tag=previous_release_tag,
            repository=repository,
            previous_revision=previous_revision,
            current_revision=current_revision,
            rationale=rationale,
        )
    return reviews


def _resolve_commit(repository_root: Path, revision: str, label: str) -> str:
    result = _run_git(repository_root, ["rev-parse", "--verify", f"{revision}^{{commit}}"])
    if result.returncode != 0:
        raise MetadataError(f"{label} does not resolve to a commit")
    return validate_commit_sha(result.stdout.strip(), field_name=label)


def _require_ancestor(repository_root: Path, ancestor: str, descendant: str, message: str) -> None:
    result = _run_git(repository_root, ["merge-base", "--is-ancestor", ancestor, descendant])
    if result.returncode != 0:
        raise MetadataError(message)


def _load_tagged_upstream_base(repository_root: Path, git_tag: str) -> UpstreamBase:
    result = _run_git(repository_root, ["show", f"{git_tag}:UPSTREAM_BASE.json"])
    if result.returncode != 0:
        raise MetadataError(f"previous Hangar release lacks UPSTREAM_BASE.json: {git_tag}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MetadataError(f"previous Hangar release has invalid upstream metadata: {git_tag}") from exc
    return parse_upstream_base(data)


def resolve_upstream_transition(
    *,
    repository_root: Path,
    current_tag: str,
    current_commit: str,
    release_pages: Any,
    transition_reviews: dict[str, UpstreamTransitionReview],
) -> ResolvedUpstreamTransition:
    parse_release_tag(current_tag)
    current_commit = _resolve_commit(repository_root, current_commit, "current release commit")
    current_upstream = load_upstream_base(repository_root / "UPSTREAM_BASE.json")
    validate_upstream_ancestry(
        repository_root=repository_root,
        upstream_revision=current_upstream.revision,
        release_commit=current_commit,
    )

    previous_tag = select_previous_release(release_pages, current_tag)
    transition_review = transition_reviews.get(current_tag)
    if previous_tag is None:
        if transition_review is not None:
            raise MetadataError("upstream transition review is not allowed for an initial release")
        return ResolvedUpstreamTransition(
            current_commit=current_commit,
            current_upstream=current_upstream,
            previous_tag=None,
            previous_commit=None,
            previous_upstream=None,
            review=None,
            is_linear=True,
        )

    previous_commit = _resolve_commit(
        repository_root, f"refs/tags/{previous_tag}", "previous release tag"
    )
    _require_ancestor(
        repository_root,
        previous_commit,
        current_commit,
        "the latest published Hangar release is not an ancestor of the current release",
    )
    previous_upstream = _load_tagged_upstream_base(repository_root, previous_tag)
    upstream_is_linear = (
        _run_git(
            repository_root,
            ["merge-base", "--is-ancestor", previous_upstream.revision, current_upstream.revision],
        ).returncode
        == 0
    )
    if upstream_is_linear:
        if transition_review is not None:
            raise MetadataError("upstream transition review is not allowed for a linear history")
    else:
        _require_ancestor(
            repository_root,
            previous_upstream.revision,
            current_commit,
            "previous upstream baseline is not present in the current release history",
        )
        expected_review = UpstreamTransitionReview(
            release_tag=current_tag,
            previous_release_tag=previous_tag,
            repository=current_upstream.repository,
            previous_revision=previous_upstream.revision,
            current_revision=current_upstream.revision,
            rationale=transition_review.rationale if transition_review is not None else "",
        )
        if transition_review != expected_review:
            raise MetadataError("upstream baselines are not linear and lack an exact maintainer review")

    return ResolvedUpstreamTransition(
        current_commit=current_commit,
        current_upstream=current_upstream,
        previous_tag=previous_tag,
        previous_commit=previous_commit,
        previous_upstream=previous_upstream,
        review=transition_review,
        is_linear=upstream_is_linear,
    )


def _escape_markdown(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;")


def _commit_lines(repository_root: Path, start: str, end: str) -> list[str]:
    result = _run_git(
        repository_root,
        ["log", "--first-parent", "--reverse", "--format=%H%x09%s", f"{start}..{end}"],
    )
    if result.returncode != 0:
        raise MetadataError("Git could not generate the release change list")
    lines = []
    for line in result.stdout.splitlines():
        commit_sha, separator, subject = line.partition("\t")
        validate_commit_sha(commit_sha, field_name="changelog commit")
        if not separator:
            raise MetadataError("Git returned malformed changelog data")
        lines.append(
            f"- {_escape_markdown(subject)} "
            f"([`{commit_sha[:12]}`]({HANGAR_REPOSITORY}/commit/{commit_sha}))"
        )
    return lines


def generate_release_notes(
    *,
    repository_root: Path,
    current_tag: str,
    current_commit: str,
    release_pages: Any,
    curated_notes: str,
    digests: dict[str, str],
    transition_reviews: dict[str, UpstreamTransitionReview],
) -> str:
    version, is_prerelease = parse_release_tag(current_tag)
    transition = resolve_upstream_transition(
        repository_root=repository_root,
        current_tag=current_tag,
        current_commit=current_commit,
        release_pages=release_pages,
        transition_reviews=transition_reviews,
    )
    current_commit = transition.current_commit
    current_upstream = transition.current_upstream

    if transition.previous_tag is None:
        change_start = current_upstream.revision
        previous_description = "Initial Hangar release; no earlier published Hangar release exists."
        upstream_description = (
            f"Initial upstream baseline: "
            f"[`{current_upstream.revision}`]({current_upstream.repository}/commit/{current_upstream.revision})."
        )
    else:
        if transition.previous_commit is None or transition.previous_upstream is None:
            raise MetadataError("resolved upstream transition is incomplete")
        previous_upstream = transition.previous_upstream
        change_start = transition.previous_commit
        previous_description = f"Changes since `{transition.previous_tag}`."
        if transition.is_linear:
            upstream_description = (
                f"Plane changes: [`{previous_upstream.revision[:12]}...{current_upstream.revision[:12]}`]"
                f"({current_upstream.repository}/compare/{previous_upstream.revision}...{current_upstream.revision})."
            )
        else:
            if transition.review is None:
                raise MetadataError("resolved non-linear upstream transition lacks a review")
            upstream_description = (
                "Plane baseline transition was maintainer-reviewed because the histories are not linear: "
                f"[`{previous_upstream.revision[:12]}`]"
                f"({current_upstream.repository}/commit/{previous_upstream.revision}) to "
                f"[`{current_upstream.revision[:12]}`]"
                f"({current_upstream.repository}/commit/{current_upstream.revision}). "
                f"Rationale: {_escape_markdown(transition.review.rationale)}"
            )

    change_lines = _commit_lines(repository_root, change_start, current_commit)
    if not change_lines:
        change_lines = ["- No source changes were detected in the controlled comparison range."]

    digest_lines = [f"- `{IMAGE_PREFIX}{image}@{digests[image]}`" for image in IMAGE_NAMES]
    prerelease_notice = (
        "This is a prerelease and does not update the `stable` image tag."
        if is_prerelease
        else "This stable release updates `stable` only after release publication succeeds."
    )
    identity = (
        f"{HANGAR_REPOSITORY}/.github/workflows/build-branch.yml@refs/tags/{current_tag}"
    )
    verification_command = "\n".join(
        (
            "```sh",
            "cosign verify \\",
            f"  --certificate-identity '{identity}' \\",
            "  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' \\",
            f"  '{IMAGE_PREFIX}<image>@sha256:<digest>'",
            "```",
        )
    )

    sections = [
        f"# Hangar {version}",
        "## Hangar changes",
        previous_description,
        "\n".join(change_lines),
        "## Upstream Plane baseline",
        f"- Repository: `{current_upstream.repository}`",
        f"- Exact revision: `{current_upstream.revision}`",
        f"- Package version: `{current_upstream.package_version}` (informational)",
        f"- Sync date: `{current_upstream.synced_at}`",
        upstream_description,
        curated_notes,
        "## Release assets and image families",
        "Release assets contain the Hangar setup, restore, Docker Compose, environment, and Swarm tools.",
        "All container images target `linux/amd64`:",
        "\n".join(digest_lines),
        prerelease_notice,
        "## Verification",
        "Each digest includes an SBOM and GitHub build-provenance attestation and is signed with Cosign.",
        "Verify a digest with:",
        verification_command,
    ]
    return "\n\n".join(section for section in sections if section) + "\n"


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--git-tag", required=True)
    validate_parser.add_argument("--commit-sha", required=True)
    validate_parser.add_argument("--release-pages", type=Path, required=True)
    validate_parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    validate_parser.add_argument("--notes-directory", type=Path, default=Path("docs/releases"))
    validate_parser.add_argument(
        "--transition-reviews",
        type=Path,
        default=Path("docs/releases/upstream-transition-reviews.json"),
    )

    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--git-tag", required=True)
    generate_parser.add_argument("--commit-sha", required=True)
    generate_parser.add_argument("--release-pages", type=Path, required=True)
    generate_parser.add_argument("--digests", type=Path, required=True)
    generate_parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    generate_parser.add_argument("--notes-directory", type=Path, default=Path("docs/releases"))
    generate_parser.add_argument(
        "--transition-reviews",
        type=Path,
        default=Path("docs/releases/upstream-transition-reviews.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = create_argument_parser().parse_args(argv)
    try:
        repository_root = arguments.repository_root.resolve(strict=True)
        notes_directory = arguments.notes_directory
        if not notes_directory.is_absolute():
            notes_directory = repository_root / notes_directory
        transition_reviews_path = arguments.transition_reviews
        if not transition_reviews_path.is_absolute():
            transition_reviews_path = repository_root / transition_reviews_path
        transition_reviews = load_upstream_transition_reviews(transition_reviews_path)
        if arguments.command == "validate":
            load_curated_notes(notes_directory, arguments.git_tag)
            release_pages = json.loads(arguments.release_pages.read_text(encoding="utf-8"))
            resolve_upstream_transition(
                repository_root=repository_root,
                current_tag=arguments.git_tag,
                current_commit=arguments.commit_sha,
                release_pages=release_pages,
                transition_reviews=transition_reviews,
            )
            return 0

        curated_notes = load_curated_notes(notes_directory, arguments.git_tag)
        release_pages = json.loads(arguments.release_pages.read_text(encoding="utf-8"))
        digests = load_digests(arguments.digests)
        notes = generate_release_notes(
            repository_root=repository_root,
            current_tag=arguments.git_tag,
            current_commit=arguments.commit_sha,
            release_pages=release_pages,
            curated_notes=curated_notes,
            digests=digests,
            transition_reviews=transition_reviews,
        )
    except (json.JSONDecodeError, MetadataError, OSError) as exc:
        print(f"release notes error: {exc}", file=sys.stderr)
        return 2
    print(notes, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
