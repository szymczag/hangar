#!/usr/bin/env python3

# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Validate and derive Hangar release metadata without changing repository state."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Sequence


EXPECTED_UPSTREAM_REPOSITORY = "https://github.com/makeplane/plane"
MAX_OCI_TAG_LENGTH = 128
UPSTREAM_BASE_KEYS = {"repository", "revision", "package_version", "synced_at"}

_COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PACKAGE_VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]{0,63}$")
_RELEASE_TAG_PATTERN = re.compile(
    r"^hangar-v"
    r"(?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>0|[1-9][0-9]*)\."
    r"(?P<patch>0|[1-9][0-9]*)"
    r"(?:-(?P<stage>alpha|beta|rc)\.(?P<sequence>[1-9][0-9]*))?$"
)


class MetadataError(ValueError):
    """Raised when release metadata cannot be trusted."""


@dataclass(frozen=True)
class UpstreamBase:
    repository: str
    revision: str
    package_version: str
    synced_at: str


@dataclass(frozen=True)
class ReleaseMetadata:
    event_name: str
    git_tag: str | None
    is_prerelease: bool
    is_release: bool
    primary_tag: str
    release_title: str | None
    schema_version: int
    sha_tag: str
    upstream: UpstreamBase
    version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_commit_sha(value: str, *, field_name: str) -> str:
    if not _COMMIT_SHA_PATTERN.fullmatch(value):
        raise MetadataError(f"{field_name} must be a complete lowercase 40-character commit SHA")
    return value


def load_upstream_base(path: Path) -> UpstreamBase:
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise MetadataError(f"cannot read upstream baseline: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MetadataError("upstream baseline must be valid JSON") from exc

    if not isinstance(raw_data, dict):
        raise MetadataError("upstream baseline must be a JSON object")

    keys = set(raw_data)
    if keys != UPSTREAM_BASE_KEYS:
        missing = sorted(UPSTREAM_BASE_KEYS - keys)
        unexpected = sorted(keys - UPSTREAM_BASE_KEYS)
        details = []
        if missing:
            details.append(f"missing keys: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected keys: {', '.join(unexpected)}")
        raise MetadataError(f"invalid upstream baseline schema ({'; '.join(details)})")

    if not all(isinstance(raw_data[key], str) for key in UPSTREAM_BASE_KEYS):
        raise MetadataError("all upstream baseline values must be strings")

    repository = raw_data["repository"]
    if repository != EXPECTED_UPSTREAM_REPOSITORY:
        raise MetadataError("upstream baseline repository is not the approved Plane repository")

    revision = validate_commit_sha(raw_data["revision"], field_name="upstream revision")

    package_version = raw_data["package_version"]
    if not _PACKAGE_VERSION_PATTERN.fullmatch(package_version):
        raise MetadataError("upstream package version has an invalid format")

    synced_at = raw_data["synced_at"]
    try:
        parsed_date = date.fromisoformat(synced_at)
    except ValueError as exc:
        raise MetadataError("upstream sync date must use YYYY-MM-DD format") from exc
    if parsed_date.isoformat() != synced_at:
        raise MetadataError("upstream sync date must use canonical YYYY-MM-DD format")

    return UpstreamBase(
        repository=repository,
        revision=revision,
        package_version=package_version,
        synced_at=synced_at,
    )


def parse_release_tag(ref_name: str) -> tuple[str, bool]:
    match = _RELEASE_TAG_PATTERN.fullmatch(ref_name)
    if match is None:
        raise MetadataError(
            "release tag must use hangar-vMAJOR.MINOR.PATCH or an approved "
            "alpha.N, beta.N, or rc.N prerelease suffix"
        )

    version = f"v{match['major']}.{match['minor']}.{match['patch']}"
    is_prerelease = match["stage"] is not None
    if is_prerelease:
        version = f"{version}-{match['stage']}.{match['sequence']}"
    return version, is_prerelease


def normalize_preview_ref(ref_name: str) -> str:
    if not ref_name or any(ord(character) < 32 or ord(character) == 127 for character in ref_name):
        raise MetadataError("preview ref must be non-empty and contain no control characters")

    normalized = re.sub(r"[^a-z0-9._-]+", "-", ref_name.lower()).strip(".-")
    if not normalized:
        raise MetadataError("preview ref cannot be converted to a safe OCI tag")

    prefix = "preview-"
    if len(prefix) + len(normalized) <= MAX_OCI_TAG_LENGTH:
        return f"{prefix}{normalized}"

    digest_suffix = hashlib.sha256(ref_name.encode("utf-8")).hexdigest()[:12]
    max_stem_length = MAX_OCI_TAG_LENGTH - len(prefix) - len(digest_suffix) - 1
    stem = normalized[:max_stem_length].rstrip(".-")
    if not stem:
        raise MetadataError("preview ref cannot be shortened to a safe OCI tag")
    return f"{prefix}{stem}-{digest_suffix}"


def build_release_metadata(
    *,
    event_name: str,
    ref_name: str,
    commit_sha: str,
    upstream: UpstreamBase,
) -> ReleaseMetadata:
    commit_sha = validate_commit_sha(commit_sha, field_name="release commit")
    sha_tag = f"sha-{commit_sha}"

    if event_name == "push":
        version, is_prerelease = parse_release_tag(ref_name)
        return ReleaseMetadata(
            event_name=event_name,
            git_tag=ref_name,
            is_prerelease=is_prerelease,
            is_release=True,
            primary_tag=version,
            release_title=f"Hangar {version}",
            schema_version=1,
            sha_tag=sha_tag,
            upstream=upstream,
            version=version,
        )

    if event_name == "workflow_dispatch":
        primary_tag = normalize_preview_ref(ref_name)
        return ReleaseMetadata(
            event_name=event_name,
            git_tag=None,
            is_prerelease=False,
            is_release=False,
            primary_tag=primary_tag,
            release_title=None,
            schema_version=1,
            sha_tag=sha_tag,
            upstream=upstream,
            version=primary_tag.removeprefix("preview-"),
        )

    raise MetadataError("event name must be push or workflow_dispatch")


def _run_git(repository_root: Path, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
    )


def validate_upstream_ancestry(
    *,
    repository_root: Path,
    upstream_revision: str,
    release_commit: str,
) -> None:
    release_commit = validate_commit_sha(release_commit, field_name="release commit")
    upstream_revision = validate_commit_sha(upstream_revision, field_name="upstream revision")

    for revision, label in ((release_commit, "release commit"), (upstream_revision, "upstream revision")):
        result = _run_git(repository_root, ["cat-file", "-e", f"{revision}^{{commit}}"])
        if result.returncode != 0:
            raise MetadataError(f"{label} does not exist in the checked-out Git object graph")

    result = _run_git(
        repository_root,
        ["merge-base", "--is-ancestor", upstream_revision, release_commit],
    )
    if result.returncode == 1:
        raise MetadataError("upstream revision is not an ancestor of the release commit")
    if result.returncode != 0:
        raise MetadataError("Git could not validate upstream ancestry")


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-name", required=True, choices=("push", "workflow_dispatch"))
    parser.add_argument("--ref-name", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--upstream-base", type=Path, default=Path("UPSTREAM_BASE.json"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_argument_parser()
    arguments = parser.parse_args(argv)

    try:
        repository_root = arguments.repository_root.resolve(strict=True)
        upstream_base_path = arguments.upstream_base
        if not upstream_base_path.is_absolute():
            upstream_base_path = repository_root / upstream_base_path

        upstream = load_upstream_base(upstream_base_path)
        validate_upstream_ancestry(
            repository_root=repository_root,
            upstream_revision=upstream.revision,
            release_commit=arguments.commit_sha,
        )
        metadata = build_release_metadata(
            event_name=arguments.event_name,
            ref_name=arguments.ref_name,
            commit_sha=arguments.commit_sha,
            upstream=upstream,
        )
    except (MetadataError, OSError) as exc:
        print(f"release metadata error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(metadata.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
