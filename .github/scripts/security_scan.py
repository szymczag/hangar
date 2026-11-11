#!/usr/bin/env python3

# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Helpers for the release image scan in .github/workflows/security-scan.yml.

resolve    picks the newest published GitHub Release, whose images are
           guaranteed to exist: the release workflow creates the Release only
           after every image is pushed, signed and verified.
summarize  turns one Trivy JSON report into a findings file, a job summary
           and, optionally, a failing exit status.
report     keeps a single tracking issue in step with the latest scan.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

from release_metadata import _RELEASE_TAG_PATTERN, MetadataError, parse_release_tag


IMAGE_NAMES = ("web", "admin", "space", "live", "api", "proxy")
ISSUE_LABEL = "security-scan"
ISSUE_TITLE = "Release image vulnerabilities"
_MARKER_PREFIX = "<!-- security-scan:release-images"
_MARKER_PATTERN = re.compile(r"<!-- security-scan:release-images fingerprint=([0-9a-f]+) -->")
_STAGE_RANK = {"alpha": 0, "beta": 1, "rc": 2, None: 3}


class ScanError(ValueError):
    """Raised when scan input cannot be interpreted."""


@dataclass(frozen=True)
class Finding:
    image: str
    vulnerability: str
    severity: str
    package: str
    installed: str
    fixed: str
    title: str
    url: str

    def to_dict(self) -> dict[str, str]:
        return {
            "image": self.image,
            "vulnerability": self.vulnerability,
            "severity": self.severity,
            "package": self.package,
            "installed": self.installed,
            "fixed": self.fixed,
            "title": self.title,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Finding":
        try:
            return cls(**{field: str(data[field]) for field in cls.__dataclass_fields__})
        except KeyError as error:
            raise ScanError(f"finding is missing {error.args[0]!r}") from error


@dataclass(frozen=True)
class Action:
    kind: str  # "create", "edit", "comment" or "close"
    body: str
    number: int | None = None


# ---------------------------------------------------------------------------
# resolve


def _release_sort_key(tag: str) -> tuple[int, int, int, int, int]:
    match = _RELEASE_TAG_PATTERN.fullmatch(tag)
    assert match is not None
    return (
        int(match["major"]),
        int(match["minor"]),
        int(match["patch"]),
        _STAGE_RANK[match["stage"]],
        int(match["sequence"] or 0),
    )


def select_latest_release(releases: Iterable[Mapping[str, Any]]) -> tuple[str, str]:
    """Return (git tag, product version) of the newest published Hangar release."""
    candidates = []
    for release in releases:
        tag = str(release.get("tagName", ""))
        if release.get("isDraft"):
            continue
        try:
            parse_release_tag(tag)
        except MetadataError:
            continue
        candidates.append(tag)
    if not candidates:
        raise ScanError("no published Hangar release found")
    tag = max(candidates, key=_release_sort_key)
    version, _ = parse_release_tag(tag)
    return tag, version


# ---------------------------------------------------------------------------
# summarize


def parse_trivy_report(report: Mapping[str, Any], image: str) -> list[Finding]:
    """Collect the vulnerabilities of a Trivy JSON report, deduplicated and sorted."""
    if "Results" not in report and "ArtifactName" not in report:
        raise ScanError("not a Trivy JSON report")
    findings = set()
    for result in report.get("Results") or []:
        for vulnerability in result.get("Vulnerabilities") or []:
            findings.add(
                Finding(
                    image=image,
                    vulnerability=str(vulnerability.get("VulnerabilityID", "")),
                    severity=str(vulnerability.get("Severity", "")),
                    package=str(vulnerability.get("PkgName", "")),
                    installed=str(vulnerability.get("InstalledVersion", "")),
                    fixed=str(vulnerability.get("FixedVersion", "")),
                    title=str(vulnerability.get("Title", "")),
                    url=str(vulnerability.get("PrimaryURL", "")),
                )
            )
    return sorted(findings, key=lambda f: (f.image, f.vulnerability, f.package))


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip() or "-"


def render_table(findings: Sequence[Finding]) -> str:
    lines = [
        "| Image | Vulnerability | Severity | Package | Installed | Fixed |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for finding in findings:
        vulnerability = _cell(finding.vulnerability)
        if finding.url:
            vulnerability = f"[{vulnerability}]({finding.url})"
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(finding.image),
                    vulnerability,
                    _cell(finding.severity),
                    _cell(finding.package),
                    _cell(finding.installed),
                    _cell(finding.fixed),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def render_step_summary(image: str, image_ref: str, findings: Sequence[Finding]) -> str:
    if not findings:
        return f"### `{image}`: clean\n\nNo fixable HIGH or CRITICAL vulnerability in `{image_ref}`.\n"
    return (
        f"### `{image}`: {len(findings)} finding(s)\n\n"
        f"Fixable HIGH or CRITICAL vulnerabilities in `{image_ref}`:\n\n"
        f"{render_table(findings)}\n"
    )


# ---------------------------------------------------------------------------
# report


def fingerprint(findings: Iterable[Finding]) -> str:
    keys = sorted({f"{f.image}|{f.vulnerability}|{f.package}" for f in findings})
    return hashlib.sha256("\n".join(keys).encode("utf-8")).hexdigest()[:16]


def read_fingerprint(body: str) -> str | None:
    match = _MARKER_PATTERN.search(body or "")
    return match[1] if match else None


def render_issue_body(
    *,
    tag: str,
    findings: Sequence[Finding],
    errors: Sequence[str],
    run_url: str,
    code_scanning_url: str,
) -> str:
    parts = [
        f"{_MARKER_PREFIX} fingerprint={fingerprint(findings)} -->",
        f"The image scan found fixable HIGH or CRITICAL vulnerabilities in the published images of `{tag}`.",
        "",
        render_table(findings),
        "",
    ]
    if errors:
        parts += [
            "Not scanned in the latest run: " + ", ".join(f"`{image}`" for image in errors) + ".",
            "",
        ]
    parts += [
        f"Latest scan: {run_url}",
        f"Each finding is also a [code scanning alert]({code_scanning_url}).",
        "",
        "These are packages inside the published images, which Dependabot does not track. "
        "A new release fixes them: every release build refreshes the Alpine packages, "
        "and other components need their pinned version raised.",
        "",
        "The Security scan workflow maintains this issue and closes it once a scan of "
        "the latest release is clean.",
    ]
    return "\n".join(parts) + "\n"


def _describe_change(previous: Sequence[Finding], current: Sequence[Finding]) -> str:
    before = {(f.image, f.vulnerability) for f in previous}
    after = {(f.image, f.vulnerability) for f in current}
    lines = []
    added = sorted(after - before)
    resolved = sorted(before - after)
    if added:
        lines.append("New: " + ", ".join(f"`{image}` {vuln}" for image, vuln in added) + ".")
    if resolved:
        lines.append("No longer found: " + ", ".join(f"`{image}` {vuln}" for image, vuln in resolved) + ".")
    return " ".join(lines)


def parse_issue_findings(body: str) -> list[Finding]:
    """Recover (image, vulnerability) pairs from a body this script rendered."""
    findings = []
    for line in (body or "").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
        if len(cells) != 6 or cells[0] in ("Image", "---"):
            continue
        vulnerability = re.sub(r"^\[(.*)\]\(.*\)$", r"\1", cells[1])
        findings.append(Finding(cells[0], vulnerability, cells[2], cells[3], cells[4], cells[5], "", ""))
    return findings


def plan_report(
    *,
    existing: Mapping[str, Any] | None,
    tag: str,
    findings: Sequence[Finding],
    errors: Sequence[str],
    run_url: str,
    code_scanning_url: str,
) -> list[Action]:
    """Decide how the tracking issue follows this scan.

    - Findings and no open issue: open one.
    - Findings and an open issue: refresh its body; comment only when the set of
      (image, vulnerability, package) changed, so a daily rerun stays quiet.
    - Any image not scanned: never close and never report a finding as gone,
      because the missing image may still carry it.
    - Every image scanned and clean: close the open issue.
    """
    body = render_issue_body(
        tag=tag,
        findings=findings,
        errors=errors,
        run_url=run_url,
        code_scanning_url=code_scanning_url,
    )
    if errors:
        if findings and existing is None:
            return [Action("create", body)]
        return []
    if findings:
        if existing is None:
            return [Action("create", body)]
        number = int(existing["number"])
        actions = [Action("edit", body, number)]
        if read_fingerprint(str(existing.get("body", ""))) != fingerprint(findings):
            change = _describe_change(parse_issue_findings(str(existing.get("body", ""))), findings)
            actions.append(Action("comment", f"The findings changed in the scan of `{tag}`. {change}\n\n{run_url}", number))
        return actions
    if existing is not None:
        return [
            Action(
                "close",
                f"The scan of `{tag}` found no fixable HIGH or CRITICAL vulnerability in any release image.\n\n{run_url}",
                int(existing["number"]),
            )
        ]
    return []


def collect_results(findings_dir: Path, images: Sequence[str]) -> tuple[list[Finding], list[str]]:
    """Read findings-<image>.json files; an image without one was not scanned."""
    findings: list[Finding] = []
    errors: list[str] = []
    for image in images:
        path = findings_dir / f"findings-{image}.json"
        if not path.is_file():
            errors.append(image)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("image") != image:
            raise ScanError(f"{path} describes {data.get('image')!r}, expected {image!r}")
        findings.extend(Finding.from_dict(item) for item in data.get("findings", []))
    return sorted(findings, key=lambda f: (f.image, f.vulnerability, f.package)), errors


# ---------------------------------------------------------------------------
# GitHub CLI layer


def _gh(arguments: Sequence[str], *, stdin: str | None = None) -> str:
    completed = subprocess.run(
        ["gh", *arguments],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ScanError(f"gh {' '.join(arguments[:2])} failed: {completed.stderr.strip()}")
    return completed.stdout


def find_tracking_issue(repository: str) -> dict[str, Any] | None:
    issues = json.loads(
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
    tracked = [issue for issue in issues if _MARKER_PREFIX in str(issue.get("body", ""))]
    return min(tracked, key=lambda issue: issue["number"]) if tracked else None


def apply_actions(repository: str, actions: Sequence[Action]) -> None:
    for action in actions:
        if action.kind == "create":
            _gh(
                [
                    "label",
                    "create",
                    ISSUE_LABEL,
                    "--repo",
                    repository,
                    "--color",
                    "B60205",
                    "--description",
                    "Tracked by the Security scan workflow",
                    "--force",
                ]
            )
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
            raise ScanError(f"unknown action {action.kind!r}")


# ---------------------------------------------------------------------------
# command line


def _write_summary(path: str | None, text: str) -> None:
    """Append to the job summary file when given, else print."""
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)


def _command_resolve(arguments: argparse.Namespace) -> int:
    releases = json.load(sys.stdin)
    tag, version = select_latest_release(releases)
    print(f"tag={tag}")
    print(f"version={version}")
    return 0


def _command_summarize(arguments: argparse.Namespace) -> int:
    report = json.loads(Path(arguments.report).read_text(encoding="utf-8"))
    findings = parse_trivy_report(report, arguments.image)
    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "image": arguments.image,
                "image_ref": arguments.image_ref,
                "findings": [finding.to_dict() for finding in findings],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_summary(arguments.step_summary, render_step_summary(arguments.image, arguments.image_ref, findings))
    if findings and arguments.fail_on_findings:
        # Workflow commands are read from stdout only.
        print(
            f"::error title=Release image vulnerabilities::{arguments.image_ref} has "
            f"{len(findings)} fixable HIGH or CRITICAL vulnerability finding(s)"
        )
        return 1
    return 0


def _command_report(arguments: argparse.Namespace) -> int:
    images = [image for image in arguments.images.split(",") if image]
    findings, errors = collect_results(Path(arguments.findings_dir), images)
    existing = find_tracking_issue(arguments.repository)
    actions = plan_report(
        existing=existing,
        tag=arguments.tag,
        findings=findings,
        errors=errors,
        run_url=arguments.run_url,
        code_scanning_url=f"https://github.com/{arguments.repository}/security/code-scanning?query=is%3Aopen+tool%3ATrivy",
    )
    apply_actions(arguments.repository, actions)
    summary = ", ".join(action.kind for action in actions) or "no change"
    _write_summary(
        arguments.step_summary,
        f"Tracking issue: {summary}. Findings: {len(findings)}. Not scanned: {', '.join(errors) or 'none'}.\n",
    )
    return 0


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    resolve = commands.add_parser("resolve", help="read `gh release list --json tagName,isDraft` on stdin")
    resolve.set_defaults(handler=_command_resolve)

    summarize = commands.add_parser("summarize")
    summarize.add_argument("--image", required=True, choices=IMAGE_NAMES)
    summarize.add_argument("--image-ref", required=True)
    summarize.add_argument("--report", required=True)
    summarize.add_argument("--output", required=True)
    summarize.add_argument("--fail-on-findings", action="store_true")
    summarize.add_argument("--step-summary", help="file to append the Markdown summary to")
    summarize.set_defaults(handler=_command_summarize)

    report = commands.add_parser("report")
    report.add_argument("--repository", required=True)
    report.add_argument("--tag", required=True)
    report.add_argument("--run-url", required=True)
    report.add_argument("--findings-dir", required=True)
    report.add_argument("--images", default=",".join(IMAGE_NAMES))
    report.add_argument("--step-summary", help="file to append the outcome to")
    report.set_defaults(handler=_command_report)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = create_argument_parser().parse_args(argv)
    try:
        return arguments.handler(arguments)
    except (ScanError, OSError, json.JSONDecodeError) as error:
        print(f"::error::{error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
