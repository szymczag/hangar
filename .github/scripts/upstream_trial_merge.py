#!/usr/bin/env python3

# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Report the conflicts an upstream release would raise, without merging it.

Hangar absorbs upstream releases as signed squash commits, so Git's own merge
base with upstream never advances (FORK.md, "Upstream maintenance loop"). This
script runs the trial merge FORK.md describes with an explicit merge base:

    git merge-tree --write-tree -z --name-only --merge-base BASE OURS THEIRS

and groups the conflicts it reports by conflict kind (content, modify/delete,
rename/delete, add/add, ...) and by area (apps/<name>, packages/<name>, else
the top-level directory), so a sync can be planned as several pull requests.

It is read-only: `git merge-tree --write-tree` writes the merged tree and blob
objects to the object database but touches no ref, index or working tree.

Example:

    git fetch upstream --tags
    python3 .github/scripts/upstream_trial_merge.py \\
        --upstream-ref v1.5.0 --merge-base v1.4.3
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

# Directories whose children are separate deployable or publishable units.
GROUPED_ROOTS = frozenset({"apps", "packages"})
ROOT_AREA = "(root)"
_CONFLICT_PATTERN = re.compile(r"^CONFLICT \(([^)]+)\)")


class TrialMergeError(RuntimeError):
    """Raised when Git cannot run the trial merge or its output is malformed."""


@dataclass(frozen=True)
class ConflictMessage:
    """One `CONFLICT (...)` message and the paths Git attached to it."""

    kind: str
    paths: tuple[str, ...]
    message: str


@dataclass
class TrialMergeResult:
    tree: str
    conflicted_files: list[str] = field(default_factory=list)
    conflicts: list[ConflictMessage] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.conflicted_files and not self.conflicts


def area_for(path: str) -> str:
    """Name the area a path belongs to: apps/<x>, packages/<x>, else its top directory."""
    parts = path.split("/")
    if len(parts) == 1:
        return ROOT_AREA
    if parts[0] in GROUPED_ROOTS and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def conflict_kind(message: str, fallback: str) -> str:
    """Return the kind from a `CONFLICT (kind): ...` message.

    The human-readable message is more specific than the -z type field, which
    reports add/add as `contents`, so it wins when both are present.
    """
    match = _CONFLICT_PATTERN.match(message)
    if match:
        return match.group(1)
    match = _CONFLICT_PATTERN.match(fallback)
    if match:
        return match.group(1)
    return fallback


def parse_merge_tree_output(output: str) -> TrialMergeResult:
    """Parse `git merge-tree --write-tree -z --name-only` output.

    Layout (git-merge-tree(1), "OUTPUT"): the tree OID, then each conflicted
    path, then an empty field, then informational messages as
    <path-count> <path>... <type> <message>, every field NUL-terminated.
    """
    fields = output.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if not fields or not re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", fields[0]):
        raise TrialMergeError("merge-tree output does not start with a tree object ID")

    result = TrialMergeResult(tree=fields[0])
    index = 1
    while index < len(fields) and fields[index] != "":
        result.conflicted_files.append(fields[index])
        index += 1
    index += 1  # the empty field closing the conflicted-file section

    while index < len(fields):
        try:
            path_count = int(fields[index])
        except ValueError as error:
            raise TrialMergeError(f"expected a path count, got {fields[index]!r}") from error
        paths = fields[index + 1 : index + 1 + path_count]
        index += 1 + path_count
        if len(paths) != path_count or index + 1 >= len(fields):
            raise TrialMergeError("merge-tree output ends inside an informational message")
        message_type, message = fields[index], fields[index + 1].rstrip("\n")
        index += 2
        if message_type.startswith("CONFLICT") or message.startswith("CONFLICT"):
            result.conflicts.append(
                ConflictMessage(kind=conflict_kind(message, message_type), paths=tuple(paths), message=message)
            )
    return result


def group_by_kind(result: TrialMergeResult) -> dict[str, list[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for conflict in result.conflicts:
        groups[conflict.kind].update(conflict.paths)
    return {kind: sorted(paths) for kind, paths in sorted(groups.items())}


def group_by_area(result: TrialMergeResult) -> dict[str, list[str]]:
    paths = set(result.conflicted_files)
    for conflict in result.conflicts:
        paths.update(conflict.paths)
    groups: dict[str, list[str]] = defaultdict(list)
    for path in sorted(paths):
        groups[area_for(path)].append(path)
    # Largest areas first, so the report opens with where the work is.
    return dict(sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])))


def build_report(result: TrialMergeResult, refs: dict[str, str]) -> dict[str, object]:
    return {
        "refs": refs,
        "tree": result.tree,
        "clean": result.clean,
        "conflicted_file_count": len(result.conflicted_files),
        "conflicted_files": sorted(result.conflicted_files),
        "by_kind": group_by_kind(result),
        "by_area": group_by_area(result),
        "messages": [conflict.message for conflict in result.conflicts],
    }


def render_text(report: dict[str, object]) -> str:
    refs = report["refs"]
    assert isinstance(refs, dict)
    lines = [
        "Upstream trial merge",
        f"  merge base: {refs['merge_base']} ({refs['merge_base_commit']})",
        f"  ours:       {refs['ours']} ({refs['ours_commit']})",
        f"  upstream:   {refs['upstream']} ({refs['upstream_commit']})",
        f"  tree:       {report['tree']}",
        "",
    ]
    if report["clean"]:
        lines.append("No conflicts.")
        return "\n".join(lines) + "\n"

    lines.append(f"{report['conflicted_file_count']} conflicted file(s).")
    for title, key in (("By kind", "by_kind"), ("By area", "by_area")):
        groups = report[key]
        assert isinstance(groups, dict)
        lines.extend(["", f"{title}:"])
        for name, paths in groups.items():
            lines.append(f"  {name} ({len(paths)})")
            lines.extend(f"    {path}" for path in paths)
    return "\n".join(lines) + "\n"


def run_git(arguments: Sequence[str], cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=cwd, check=False, capture_output=True, text=True, encoding="utf-8"
    )


def resolve_commit(reference: str, cwd: str | None = None) -> str:
    # --end-of-options keeps a reference that starts with "-" from being read as an option.
    completed = run_git(["rev-parse", "--verify", "--quiet", "--end-of-options", f"{reference}^{{commit}}"], cwd)
    if completed.returncode != 0:
        raise TrialMergeError(f"cannot resolve {reference!r} to a commit (fetch upstream tags first?)")
    return completed.stdout.strip()


def trial_merge(upstream_ref: str, merge_base: str, ours: str = "HEAD", cwd: str | None = None) -> dict[str, object]:
    commits = {
        "upstream": resolve_commit(upstream_ref, cwd),
        "merge_base": resolve_commit(merge_base, cwd),
        "ours": resolve_commit(ours, cwd),
    }
    completed = run_git(
        [
            "merge-tree",
            "--write-tree",
            "-z",
            "--name-only",
            f"--merge-base={commits['merge_base']}",
            commits["ours"],
            commits["upstream"],
        ],
        cwd,
    )
    # 0 is a clean merge and 1 a merge with conflicts; anything else is an error.
    if completed.returncode not in (0, 1):
        raise TrialMergeError(f"git merge-tree failed: {completed.stderr.strip()}")
    result = parse_merge_tree_output(completed.stdout)
    refs = {
        "upstream": upstream_ref,
        "upstream_commit": commits["upstream"],
        "merge_base": merge_base,
        "merge_base_commit": commits["merge_base"],
        "ours": ours,
        "ours_commit": commits["ours"],
    }
    return build_report(result, refs)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upstream-ref", required=True, help="upstream release to trial, e.g. v1.5.0")
    parser.add_argument(
        "--merge-base", required=True, help="upstream release Hangar last absorbed, e.g. v1.4.3"
    )
    parser.add_argument("--ours", default="HEAD", help="Hangar commit to merge into (default: HEAD)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = create_argument_parser().parse_args(argv)
    try:
        report = trial_merge(arguments.upstream_ref, arguments.merge_base, arguments.ours)
    except TrialMergeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
