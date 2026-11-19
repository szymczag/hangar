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
validate-ignores
           checks that every accepted finding in .trivyignore.yaml carries an
           id, a statement and an expiry no more than 180 days ahead, so an
           exception cannot outlive its review, and that every accepted secret
           names the exact files it covers.
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

from release_metadata import _RELEASE_TAG_PATTERN, MetadataError, parse_release_tag


IMAGE_NAMES = ("web", "admin", "space", "live", "api", "proxy")
ISSUE_LABEL = "security-scan"
ISSUE_TITLE = "Release image vulnerabilities"
_MARKER_PREFIX = "<!-- security-scan:release-images"
_MARKER_PATTERN = re.compile(r"<!-- security-scan:release-images fingerprint=([0-9a-f]+) -->")
_STAGE_RANK = {"alpha": 0, "beta": 1, "rc": 2, None: 3}
IGNORE_FILE = ".trivyignore.yaml"
IGNORE_MAX_DAYS = 180
# The top-level keys of .trivyignore.yaml that Hangar accepts, with the keys
# each entry needs and the list keys it may carry. Secrets must name their
# files: a secret exception without `paths` would hide that rule everywhere.
IGNORE_SECTIONS: Mapping[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "vulnerabilities": (("id", "statement", "expired_at"), ("paths", "purls")),
    "secrets": (("id", "paths", "statement", "expired_at"), ("paths",)),
}
# Trivy's built-in secret rule ids, e.g. `private-key` or `aws-access-key-id`.
_SECRET_RULE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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
# validate-ignores
#
# .trivyignore.yaml is read with a strict parser for the small YAML subset the
# file uses, not with PyYAML: the runners' system Python does not promise
# PyYAML, and installing a package just to read one fixed-shape file would add
# a download and a supply-chain input to a security gate. Anything outside the
# subset is rejected with its line number instead of being guessed at, so the
# validator never accepts a file that Trivy might read differently. The tests
# compare the result with PyYAML where it is installed.
#
#   vulnerabilities:          top-level keys: `vulnerabilities` and
#     - id: CVE-...           `secrets`, each at most once, in any order
#       paths:                optional lists of plain or quoted scalars
#         - apps/api/x.toml
#       statement: >-         plain, quoted or folded (>, >-) scalars
#         folded text
#       expired_at: 2027-01-31
#   secrets:
#     - id: private-key       a Trivy secret rule id
#       paths:                required: exact file paths as Trivy reports
#         - "/app/x/index.js" the target, absolute inside an image
#       statement: ...
#       expired_at: 2027-01-31


class IgnoreFileError(ScanError):
    """Raised when .trivyignore.yaml is outside the supported YAML subset."""


_KEY_PATTERN = re.compile(r"^(?P<key>[a-z_]+):(?:[ ](?P<value>.*))?$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _scalar(text: str, number: int) -> str:
    """Parse a flow scalar: plain (with an optional ` #` comment) or quoted."""
    text = text.strip()
    if text[:1] in ('"', "'"):
        quote = text[0]
        end = text.find(quote, 1)
        if end == -1 or "\\" in text[1:end] or (quote == "'" and text[end : end + 2] == "''"):
            raise IgnoreFileError(f"line {number}: unsupported quoted scalar {text!r}")
        rest = text[end + 1 :].strip()
        if rest and not rest.startswith("#"):
            raise IgnoreFileError(f"line {number}: unexpected text after the quoted scalar")
        return text[1:end]
    text = re.split(r"\s#", text, maxsplit=1)[0].strip()
    if not text or text[0] in "&*!|>[]{}%@`,?-" or ": " in text or text.endswith(":"):
        raise IgnoreFileError(f"line {number}: unsupported value {text!r}; quote it")
    return text


def parse_ignore_file(text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse a .trivyignore.yaml into its sections, each a list of exceptions."""
    lines = [(number, line.rstrip()) for number, line in enumerate(text.splitlines(), start=1)]
    for number, line in lines:
        if "\t" in line:
            raise IgnoreFileError(f"line {number}: tabs are not allowed")
    content = [(n, l) for n, l in lines if l.strip() and not l.lstrip().startswith("#")]
    supported = ", ".join(f"`{name}`" for name in IGNORE_SECTIONS)
    if not content or _indent(content[0][1]) != 0:
        raise IgnoreFileError(f"the file must start with a top-level key: {supported}")
    sections: dict[str, list[dict[str, Any]]] = {}
    entries: list[dict[str, Any]] = []
    item_indent: int | None = None
    position = 0
    while position < len(content):
        number, line = content[position]
        indent = _indent(line)
        stripped = line.strip()
        if indent == 0:
            section = stripped[:-1] if stripped.endswith(":") else ""
            if section not in IGNORE_SECTIONS:
                raise IgnoreFileError(f"line {number}: only {supported} are supported at the top level")
            if section in sections:
                raise IgnoreFileError(f"line {number}: `{section}` is listed more than once")
            if sections and not entries:
                raise IgnoreFileError(f"line {number}: the previous section has no exceptions")
            entries = sections.setdefault(section, [])
            item_indent = None
            position += 1
            continue
        if stripped.startswith("- "):
            # A list item opens a new exception; its first key sits after "- ".
            item_indent = indent if item_indent is None else item_indent
            if indent != item_indent:
                raise IgnoreFileError(f"line {number}: inconsistent list indentation")
            entries.append({})
            stripped = stripped[2:].lstrip()
        elif not entries or indent != item_indent + 2:
            raise IgnoreFileError(f"line {number}: expected `- id: ...` or a key of the current exception")
        key_indent = item_indent + 2
        match = _KEY_PATTERN.match(stripped)
        if match is None:
            raise IgnoreFileError(f"line {number}: expected `key: value`")
        key, value = match["key"], (match["value"] or "").strip()
        entry = entries[-1]
        if key in entry:
            raise IgnoreFileError(f"line {number}: duplicate key {key!r}")
        position += 1
        # The lines that belong to this key are indented deeper than it.
        block = []
        while position < len(content) and _indent(content[position][1]) > key_indent:
            block.append(content[position])
            position += 1
        if value in (">", ">-"):
            entry[key] = _folded(key, number, block, lines, keep_newline=value == ">")
        elif value == "":
            if not block:
                raise IgnoreFileError(f"line {number}: {key!r} has no value")
            items = []
            for item_number, item_line in block:
                item = item_line.strip()
                if not item.startswith("- "):
                    raise IgnoreFileError(f"line {item_number}: expected a `- ` list item under {key!r}")
                items.append(_scalar(item[2:], item_number))
            entry[key] = items
        elif block:
            raise IgnoreFileError(f"line {block[0][0]}: unexpected indentation")
        elif value.startswith(("|", ">")):
            raise IgnoreFileError(f"line {number}: only `>` and `>-` block scalars are supported")
        else:
            entry[key] = _scalar(value, number)
    if not entries:
        raise IgnoreFileError("the last section has no exceptions")
    return sections


def _folded(
    key: str,
    number: int,
    block: Sequence[tuple[int, str]],
    lines: Sequence[tuple[int, str]],
    *,
    keep_newline: bool,
) -> str:
    if not block:
        raise IgnoreFileError(f"line {number}: {key!r} has an empty block scalar")
    first, last = block[0][0], block[-1][0]
    # Re-read the raw lines so comment-looking text and blank lines inside the
    # block stay part of it, as YAML reads them.
    raw = [line for n, line in lines if first <= n <= last]
    text_indent = _indent(raw[0])
    paragraphs: list[list[str]] = [[]]
    for offset, line in enumerate(raw):
        if not line.strip():
            paragraphs.append([])
            continue
        if _indent(line) != text_indent:
            raise IgnoreFileError(f"line {first + offset}: folded text must keep one indentation")
        paragraphs[-1].append(line.strip())
    text = "\n".join(" ".join(paragraph) for paragraph in paragraphs if paragraph)
    return text + ("\n" if keep_newline else "")


def _secret_path_problem(path: str) -> str | None:
    """Explain why `path` is not an exact file path inside an image, or None."""
    # Trivy matches `paths` as doublestar globs against the result target,
    # which for an image is the file's absolute path. Without any glob
    # character a pattern matches only that one string.
    if not path.startswith("/"):
        return "must be absolute, as Trivy reports image files (e.g. /app/...)"
    if re.search(r"[*?\[\]{}\\]", path):
        return "must be an exact file path, not a glob"
    if path.endswith("/") or any(part in ("", ".", "..") for part in path[1:].split("/")):
        return "must be a normalised path to a file, not a directory"
    return None


def validate_ignore_entries(
    entries: Sequence[Mapping[str, Any]], today: datetime.date, section: str = "vulnerabilities"
) -> list[str]:
    """Return one message per problem in one section; an empty list means it is valid."""
    required, list_keys = IGNORE_SECTIONS[section]
    problems = []
    if not entries:
        problems.append(f"no exceptions listed under {section}; delete the file instead of leaving it empty")
    latest = today + datetime.timedelta(days=IGNORE_MAX_DAYS)
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        name = str(entry.get("id") or f"entry {index}")
        if section != "vulnerabilities":
            name = f"{section}/{name}"
        for key in required:
            value = entry.get(key)
            if value is None or (key not in list_keys and not (isinstance(value, str) and value.strip())):
                problems.append(f"{name}: missing {key}")
        for key in sorted(set(entry) - set(required) - set(list_keys)):
            problems.append(f"{name}: unsupported key {key!r}")
        for key in list_keys:
            if key in entry and not (isinstance(entry[key], list) and entry[key]):
                problems.append(f"{name}: {key} must be a non-empty list")
        if name in seen:
            problems.append(f"{name}: listed more than once")
        seen.add(name)
        if section == "secrets":
            rule = entry.get("id")
            if isinstance(rule, str) and rule and not _SECRET_RULE_PATTERN.match(rule):
                problems.append(f"{name}: id must be a Trivy secret rule id such as `private-key`")
            for path in entry.get("paths") if isinstance(entry.get("paths"), list) else []:
                problem = _secret_path_problem(path)
                if problem:
                    problems.append(f"{name}: path {path!r} {problem}")
        expiry = entry.get("expired_at")
        if not isinstance(expiry, str) or not expiry.strip():
            continue
        try:
            if not _DATE_PATTERN.match(expiry):
                raise ValueError
            expires = datetime.date.fromisoformat(expiry)
        except ValueError:
            problems.append(f"{name}: expired_at {expiry!r} is not a YYYY-MM-DD date")
            continue
        # Trivy stops honouring an exception once expired_at has passed, which
        # for a date is from its first moment.
        if expires <= today:
            problems.append(f"{name}: expired on {expires.isoformat()}; review it, then renew or remove it")
        elif expires > latest:
            problems.append(
                f"{name}: expired_at {expires.isoformat()} is more than {IGNORE_MAX_DAYS} days ahead "
                f"(latest allowed {latest.isoformat()})"
            )
    return problems


def validate_ignore_file(sections: Mapping[str, Sequence[Mapping[str, Any]]], today: datetime.date) -> list[str]:
    """Validate every section of a parsed .trivyignore.yaml."""
    if not any(sections.values()):
        return ["no exceptions listed; delete the file instead of leaving it empty"]
    problems = []
    for section, entries in sections.items():
        problems.extend(validate_ignore_entries(entries, today, section))
    return problems


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


def _command_validate_ignores(arguments: argparse.Namespace) -> int:
    path = Path(arguments.file)
    today = datetime.date.fromisoformat(arguments.today) if arguments.today else datetime.datetime.now(datetime.timezone.utc).date()
    sections = parse_ignore_file(path.read_text(encoding="utf-8"))
    problems = validate_ignore_file(sections, today)
    for problem in problems:
        # Workflow commands are read from stdout only.
        print(f"::error file={path},title=Trivy exception::{problem}")
    if problems:
        print(f"{path}: {len(problems)} problem(s); see {path} for how exceptions are reviewed.")
        return 1
    count = 0
    for section, entries in sections.items():
        for entry in entries:
            count += 1
            print(f"{section}/{entry['id']}: accepted until {entry['expired_at']}")
    print(f"{path}: {count} exception(s), each expiring within {IGNORE_MAX_DAYS} days.")
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

    validate_ignores = commands.add_parser(
        "validate-ignores",
        help=f"check that every exception in {IGNORE_FILE} has an id, a statement and a near expiry",
    )
    validate_ignores.add_argument("--file", default=IGNORE_FILE)
    validate_ignores.add_argument("--today", help="YYYY-MM-DD to validate against instead of the current UTC date")
    validate_ignores.set_defaults(handler=_command_validate_ignores)
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
