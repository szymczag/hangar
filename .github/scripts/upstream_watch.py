#!/usr/bin/env python3

# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Track what upstream Plane published since the fork's recorded baseline.

Run weekly by .github/workflows/upstream-watch.yml. It reads UPSTREAM_BASE.json,
lists the upstream releases newer than its package_version and the upstream
repository security advisories published on or after its synced_at date, and
keeps exactly one open issue labelled `upstream-sync` in step with that list:
opened when something is pending, refreshed (with a comment only when the set
changes), and closed once a sync has moved the baseline past everything.

The decision logic is pure and unit-tested with recorded API responses; only
the GitHub CLI layer at the bottom talks to the network.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

from release_metadata import MetadataError, UpstreamBase, parse_upstream_base


ISSUE_LABEL = "upstream-sync"
ISSUE_TITLE = "Upstream changes to assess"
_MARKER_PREFIX = "<!-- upstream-watch:pending"
_MARKER_PATTERN = re.compile(r"<!-- upstream-watch:pending fingerprint=([0-9a-f]+) -->")
_ITEM_PATTERN = re.compile(r"^\| (?:\[)?(?P<key>v\d+\.\d+\.\d+|GHSA(?:-[0-9a-z]{4}){3})")
_STABLE_TAG = re.compile(r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
_GITHUB_REPOSITORY = re.compile(r"^https://github\.com/(?P<slug>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$")


class WatchError(ValueError):
    """Raised when upstream data cannot be interpreted."""


@dataclass(frozen=True)
class Release:
    tag: str
    published_at: str
    url: str


@dataclass(frozen=True)
class Advisory:
    ghsa_id: str
    cve_id: str
    severity: str
    summary: str
    published_at: str
    patched: str
    url: str


@dataclass(frozen=True)
class Action:
    kind: str  # "create", "edit", "comment" or "close"
    body: str
    number: int | None = None


# ---------------------------------------------------------------------------
# decision logic


def repository_slug(repository_url: str) -> str:
    match = _GITHUB_REPOSITORY.fullmatch(repository_url)
    if match is None:
        raise WatchError(f"not a GitHub repository URL: {repository_url!r}")
    return match["slug"]


def stable_version(tag: str) -> tuple[int, int, int] | None:
    """(major, minor, patch) of a stable release tag such as v1.5.0, else None."""
    match = _STABLE_TAG.fullmatch(tag.strip())
    if match is None:
        return None
    return int(match["major"]), int(match["minor"]), int(match["patch"])


def pending_releases(releases: Iterable[Mapping[str, Any]], package_version: str) -> list[Release]:
    """Stable upstream releases newer than the baseline, oldest first.

    Drafts, prereleases and tags that are not plain X.Y.Z are not sync targets.
    """
    baseline = stable_version(package_version)
    if baseline is None:
        raise WatchError(f"baseline package_version {package_version!r} is not X.Y.Z")
    pending = []
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        tag = str(release.get("tag_name", ""))
        version = stable_version(tag)
        if version is None or version <= baseline:
            continue
        pending.append(
            (
                version,
                Release(
                    tag=tag, published_at=str(release.get("published_at") or ""), url=str(release.get("html_url", ""))
                ),
            )
        )
    return [release for _, release in sorted(pending)]


def _date_of(timestamp: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(timestamp[:10])
    except ValueError as error:
        raise WatchError(f"unreadable timestamp {timestamp!r}") from error


def pending_advisories(advisories: Iterable[Mapping[str, Any]], synced_at: str) -> list[Advisory]:
    """Published upstream advisories dated on or after the sync day, oldest first.

    The sync day itself is included: the baseline records a date, not a time,
    so an advisory published that day may postdate the synced revision.
    """
    since = _date_of(synced_at)
    pending = []
    for advisory in advisories:
        if advisory.get("state", "published") != "published":
            continue
        published_at = str(advisory.get("published_at") or "")
        if not published_at or _date_of(published_at) < since:
            continue
        patched = sorted(
            {
                str(item.get("patched_versions"))
                for item in advisory.get("vulnerabilities") or []
                if item.get("patched_versions")
            }
        )
        pending.append(
            Advisory(
                ghsa_id=str(advisory.get("ghsa_id", "")),
                cve_id=str(advisory.get("cve_id") or ""),
                severity=str(advisory.get("severity") or "unknown"),
                summary=str(advisory.get("summary", "")),
                published_at=published_at,
                patched=", ".join(patched),
                url=str(advisory.get("html_url", "")),
            )
        )
    return sorted(pending, key=lambda advisory: (advisory.published_at, advisory.ghsa_id))


def fingerprint(releases: Sequence[Release], advisories: Sequence[Advisory]) -> str:
    keys = sorted({release.tag for release in releases} | {advisory.ghsa_id for advisory in advisories})
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()[:16]


def read_fingerprint(body: str) -> str | None:
    match = _MARKER_PATTERN.search(body or "")
    return match[1] if match else None


def read_items(body: str) -> set[str]:
    """Release tags and GHSA ids listed in a body this script rendered."""
    items = set()
    for line in (body or "").splitlines():
        match = _ITEM_PATTERN.match(line.strip())
        if match:
            items.add(match["key"])
    return items


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip() or "-"


def _link(text: str, url: str) -> str:
    return f"[{_cell(text)}]({url})" if url else _cell(text)


def render_issue_body(
    *,
    baseline: UpstreamBase,
    releases: Sequence[Release],
    advisories: Sequence[Advisory],
    run_url: str,
) -> str:
    slug = repository_slug(baseline.repository)
    parts = [
        f"{_MARKER_PREFIX} fingerprint={fingerprint(releases, advisories)} -->",
        f"Upstream `{slug}` has published changes since the recorded baseline "
        f"(`{baseline.package_version}` at `{baseline.revision[:12]}`, synced {baseline.synced_at}).",
        "",
    ]
    if releases:
        parts += [
            f"### Releases newer than {baseline.package_version}",
            "",
            "| Release | Published |",
            "| --- | --- |",
        ]
        parts += [f"| {_link(release.tag, release.url)} | {_cell(release.published_at[:10])} |" for release in releases]
        parts.append("")
    if advisories:
        parts += [
            f"### Security advisories published since {baseline.synced_at}",
            "",
            "| Advisory | CVE | Severity | Patched in | Summary |",
            "| --- | --- | --- | --- | --- |",
        ]
        parts += [
            "| "
            + " | ".join(
                (
                    _link(advisory.ghsa_id, advisory.url),
                    _cell(advisory.cve_id),
                    _cell(advisory.severity),
                    _cell(advisory.patched),
                    _cell(advisory.summary),
                )
            )
            + " |"
            for advisory in advisories
        ]
        parts.append("")
    parts += [
        "Assess each item against Hangar, then either sync upstream or backport the fix with a "
        "regression test, note it in the security section of the next `docs/releases/<tag>.md`, "
        "and move `UPSTREAM_BASE.json` forward. The loop is described in FORK.md.",
        "",
        f"Latest check: {run_url}",
        "",
        "The Upstream watch workflow maintains this issue and closes it once the baseline "
        "covers every listed release and advisory.",
    ]
    return "\n".join(parts) + "\n"


def plan_issue(
    *,
    open_issues: Sequence[Mapping[str, Any]],
    baseline: UpstreamBase,
    releases: Sequence[Release],
    advisories: Sequence[Advisory],
    run_url: str,
) -> list[Action]:
    """Decide how the tracking issue follows this check.

    - Something pending and no open issue: open one.
    - Something pending and an open issue: refresh its body; comment only when
      the set of releases and advisories changed, so a weekly rerun stays quiet.
    - Nothing pending: close the open issue.
    - Further open issues carrying the marker are closed as duplicates, so
      exactly one stays open.
    """
    tracked = sorted(
        (issue for issue in open_issues if _MARKER_PREFIX in str(issue.get("body", ""))),
        key=lambda issue: int(issue["number"]),
    )
    existing = tracked[0] if tracked else None
    actions = [
        Action(
            "close",
            f"Duplicate of #{existing['number']}, which tracks the same upstream changes.",
            int(issue["number"]),
        )
        for issue in tracked[1:]
    ]
    if not releases and not advisories:
        if existing is not None:
            actions.insert(
                0,
                Action(
                    "close",
                    f"The baseline (`{baseline.package_version}`, synced {baseline.synced_at}) covers every "
                    f"upstream release and advisory.\n\n{run_url}",
                    int(existing["number"]),
                ),
            )
        return actions
    body = render_issue_body(baseline=baseline, releases=releases, advisories=advisories, run_url=run_url)
    if existing is None:
        return [Action("create", body), *actions]
    number = int(existing["number"])
    planned = [Action("edit", body, number)]
    previous_body = str(existing.get("body", ""))
    if read_fingerprint(previous_body) != fingerprint(releases, advisories):
        before = read_items(previous_body)
        after = {release.tag for release in releases} | {advisory.ghsa_id for advisory in advisories}
        change = []
        if after - before:
            change.append("New: " + ", ".join(sorted(after - before)) + ".")
        if before - after:
            change.append("No longer pending: " + ", ".join(sorted(before - after)) + ".")
        planned.append(
            Action("comment", f"The pending upstream changes changed. {' '.join(change)}\n\n{run_url}", number)
        )
    return planned + actions


# ---------------------------------------------------------------------------
# GitHub CLI layer


def _gh(arguments: Sequence[str], *, stdin: str | None = None) -> str:
    completed = subprocess.run(["gh", *arguments], input=stdin, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise WatchError(f"gh {' '.join(arguments[:2])} failed: {completed.stderr.strip()}")
    return completed.stdout


def _gh_list(path: str) -> list[dict[str, Any]]:
    """Every element of a paginated list endpoint, one JSON object per line."""
    output = _gh(["api", "--paginate", path, "--jq", ".[]"])
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def fetch_releases(slug: str) -> list[dict[str, Any]]:
    return _gh_list(f"repos/{slug}/releases?per_page=100")


def fetch_advisories(slug: str) -> list[dict[str, Any]]:
    return _gh_list(f"repos/{slug}/security-advisories?state=published&per_page=100")


def fetch_open_issues(repository: str) -> list[dict[str, Any]]:
    return json.loads(
        _gh(
            [
                "issue",
                "list",
                "--repo",
                repository,
                "--label",
                ISSUE_LABEL,
                "--state",
                "open",
                "--limit",
                "20",
                "--json",
                "number,body",
            ]
        )
    )


def apply_actions(repository: str, actions: Sequence[Action]) -> None:
    for action in actions:
        if action.kind == "create":
            _gh(
                [
                    "issue",
                    "create",
                    "--repo",
                    repository,
                    "--title",
                    ISSUE_TITLE,
                    "--label",
                    ISSUE_LABEL,
                    "--body-file",
                    "-",
                ],
                stdin=action.body,
            )
        elif action.kind == "edit":
            _gh(["issue", "edit", str(action.number), "--repo", repository, "--body-file", "-"], stdin=action.body)
        elif action.kind == "comment":
            _gh(["issue", "comment", str(action.number), "--repo", repository, "--body-file", "-"], stdin=action.body)
        elif action.kind == "close":
            _gh(["issue", "close", str(action.number), "--repo", repository, "--comment", action.body])
        else:
            raise WatchError(f"unknown action {action.kind!r}")


# ---------------------------------------------------------------------------
# command line


def _load_json(path: str | None) -> Any:
    return None if path is None else json.loads(Path(path).read_text(encoding="utf-8"))


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", default="UPSTREAM_BASE.json")
    parser.add_argument("--repository", required=True, help="owner/name of the repository holding the issue")
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--releases-json", help="read upstream releases from this file instead of the API")
    parser.add_argument("--advisories-json", help="read upstream advisories from this file instead of the API")
    parser.add_argument("--dry-run", action="store_true", help="print the planned issue actions without applying them")
    parser.add_argument("--step-summary", help="file to append the outcome to")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = create_argument_parser().parse_args(argv)
    try:
        baseline = parse_upstream_base(_load_json(arguments.baseline))
        slug = repository_slug(baseline.repository)
        raw_releases = _load_json(arguments.releases_json)
        raw_advisories = _load_json(arguments.advisories_json)
        releases = pending_releases(
            raw_releases if raw_releases is not None else fetch_releases(slug), baseline.package_version
        )
        advisories = pending_advisories(
            raw_advisories if raw_advisories is not None else fetch_advisories(slug), baseline.synced_at
        )
        open_issues = [] if arguments.dry_run else fetch_open_issues(arguments.repository)
        actions = plan_issue(
            open_issues=open_issues,
            baseline=baseline,
            releases=releases,
            advisories=advisories,
            run_url=arguments.run_url,
        )
        if arguments.dry_run:
            for action in actions:
                print(f"--- {action.kind} {action.number or ''}".rstrip())
                print(action.body)
        else:
            apply_actions(arguments.repository, actions)
    except (WatchError, MetadataError, OSError, json.JSONDecodeError) as error:
        print(f"::error::{error}")
        return 2
    summary = (
        f"Pending upstream releases: {', '.join(r.tag for r in releases) or 'none'}. "
        f"Pending advisories: {', '.join(a.ghsa_id for a in advisories) or 'none'}. "
        f"Tracking issue: {', '.join(action.kind for action in actions) or 'no change'}."
    )
    if arguments.step_summary:
        with open(arguments.step_summary, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
