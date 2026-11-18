# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SCRIPTS_DIRECTORY / "upstream_trial_merge.py"
SPEC = importlib.util.spec_from_file_location("upstream_trial_merge", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Cannot load upstream_trial_merge.py")
trial = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trial
SPEC.loader.exec_module(trial)


TREE = "033eac309c85a5a4d7e77f1b22725200fe042040"


def message(paths, kind, text):
    return [str(len(paths)), *paths, kind, text + "\n"]


# Recorded from `git merge-tree --write-tree -z --name-only` (Git 2.47) on a
# merge with a content conflict, a modify/delete, an add/add on a path with a
# space and a second content conflict; fields are NUL-terminated.
FIXTURE_FIELDS = [
    TREE,
    "apps/api/x.py",
    "del.txt",
    "docs/sp ace.md",
    "packages/ui/y.ts",
    "",
    *message(["apps/api/x.py"], "Auto-merging", "Auto-merging apps/api/x.py"),
    *message(["apps/api/x.py"], "CONFLICT (contents)", "CONFLICT (content): Merge conflict in apps/api/x.py"),
    *message(
        ["del.txt"],
        "CONFLICT (modify/delete)",
        "CONFLICT (modify/delete): del.txt deleted in main and modified in theirs.  "
        "Version theirs of del.txt left in tree.",
    ),
    *message(["docs/sp ace.md"], "Auto-merging", "Auto-merging docs/sp ace.md"),
    *message(["docs/sp ace.md"], "CONFLICT (contents)", "CONFLICT (add/add): Merge conflict in docs/sp ace.md"),
    *message(["packages/ui/y.ts"], "CONFLICT (contents)", "CONFLICT (content): Merge conflict in packages/ui/y.ts"),
]
FIXTURE = "\0".join(FIXTURE_FIELDS) + "\0"


class AreaTests(unittest.TestCase):
    def test_apps_and_packages_are_split_by_their_child(self):
        self.assertEqual(trial.area_for("apps/web/core/a.tsx"), "apps/web")
        self.assertEqual(trial.area_for("packages/editor/src/x.ts"), "packages/editor")

    def test_other_paths_use_their_top_directory(self):
        self.assertEqual(trial.area_for("deployments/cli/community/docker-compose.yml"), "deployments")
        self.assertEqual(trial.area_for(".github/workflows/build-branch.yml"), ".github")

    def test_files_at_the_root_and_directly_under_apps_share_sensible_areas(self):
        self.assertEqual(trial.area_for("package.json"), trial.ROOT_AREA)
        self.assertEqual(trial.area_for("apps/README.md"), "apps")


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.result = trial.parse_merge_tree_output(FIXTURE)

    def test_reads_tree_and_conflicted_files(self):
        self.assertEqual(self.result.tree, TREE)
        self.assertEqual(
            self.result.conflicted_files, ["apps/api/x.py", "del.txt", "docs/sp ace.md", "packages/ui/y.ts"]
        )

    def test_keeps_only_conflict_messages(self):
        self.assertEqual(len(self.result.conflicts), 4)
        self.assertTrue(all(conflict.message.startswith("CONFLICT") for conflict in self.result.conflicts))

    def test_kind_comes_from_the_message_not_the_coarser_type_field(self):
        kinds = {conflict.paths[0]: conflict.kind for conflict in self.result.conflicts}
        self.assertEqual(kinds["docs/sp ace.md"], "add/add")
        self.assertEqual(kinds["del.txt"], "modify/delete")
        self.assertEqual(kinds["apps/api/x.py"], "content")

    def test_groups_by_kind_and_area(self):
        self.assertEqual(
            trial.group_by_kind(self.result),
            {
                "add/add": ["docs/sp ace.md"],
                "content": ["apps/api/x.py", "packages/ui/y.ts"],
                "modify/delete": ["del.txt"],
            },
        )
        self.assertEqual(
            trial.group_by_area(self.result),
            {
                "(root)": ["del.txt"],
                "apps/api": ["apps/api/x.py"],
                "docs": ["docs/sp ace.md"],
                "packages/ui": ["packages/ui/y.ts"],
            },
        )

    def test_clean_merge_is_only_a_tree(self):
        result = trial.parse_merge_tree_output(TREE + "\0")
        self.assertTrue(result.clean)
        self.assertEqual(trial.group_by_kind(result), {})

    def test_rename_message_paths_all_count(self):
        output = "\0".join(
            [
                TREE,
                "apps/web/new.ts",
                "",
                *message(
                    ["apps/web/old.ts", "apps/web/new.ts"],
                    "CONFLICT (rename/delete)",
                    "CONFLICT (rename/delete): apps/web/old.ts renamed to apps/web/new.ts in theirs, "
                    "but deleted in ours.",
                ),
            ]
        ) + "\0"
        result = trial.parse_merge_tree_output(output)
        self.assertEqual(trial.group_by_kind(result), {"rename/delete": ["apps/web/new.ts", "apps/web/old.ts"]})

    def test_rejects_output_that_is_not_merge_tree(self):
        with self.assertRaises(trial.TrialMergeError):
            trial.parse_merge_tree_output("fatal: something\n")
        with self.assertRaises(trial.TrialMergeError):
            trial.parse_merge_tree_output(TREE + "\0a\0\0" + "1\0a\0CONFLICT (contents)\0")
        with self.assertRaises(trial.TrialMergeError):
            trial.parse_merge_tree_output(TREE + "\0a\0\0" + "x\0")

    def test_text_report_names_every_group(self):
        refs = {
            "upstream": "v1.5.0",
            "upstream_commit": "u",
            "merge_base": "v1.4.3",
            "merge_base_commit": "b",
            "ours": "HEAD",
            "ours_commit": "o",
        }
        text = trial.render_text(trial.build_report(self.result, refs))
        self.assertIn("4 conflicted file(s).", text)
        self.assertIn("  modify/delete (1)", text)
        self.assertIn("  packages/ui (1)", text)
        self.assertIn("v1.4.3 (b)", text)


@unittest.skipUnless(shutil.which("git"), "git is required")
class IntegrationTests(unittest.TestCase):
    """Build a tiny repository and run the script against it end to end."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name
        self.environment = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        self.git("init", "-q", "-b", "main")
        self.write("apps/api/x.py", "a\nb\nc\n")
        self.write("packages/ui/y.ts", "same\n")
        self.commit("base")
        self.git("tag", "base")
        self.git("checkout", "-q", "-b", "upstream")
        self.write("apps/api/x.py", "a\nTHEIRS\nc\n")
        self.write("packages/ui/y.ts", "upstream only\n")
        self.commit("upstream")
        self.git("checkout", "-q", "main")
        self.write("apps/api/x.py", "a\nOURS\nc\n")
        self.commit("ours")

    def tearDown(self):
        self.directory.cleanup()

    def git(self, *arguments):
        return subprocess.run(
            ["git", *arguments], cwd=self.root, env=self.environment, check=True, capture_output=True, text=True
        ).stdout

    def write(self, path, content):
        target = Path(self.root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def commit(self, subject):
        self.git("add", "-A")
        self.git("commit", "-q", "--no-gpg-sign", "-m", subject)

    def run_main(self, *arguments):
        stdout = io.StringIO()
        previous = os.getcwd()
        saved = {key: os.environ.get(key) for key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}
        os.chdir(self.root)
        os.environ.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                code = trial.main(list(arguments))
        finally:
            os.chdir(previous)
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return code, stdout.getvalue()

    def test_reports_the_conflict_and_leaves_the_repository_untouched(self):
        head = self.git("rev-parse", "HEAD")
        refs = self.git("for-each-ref")
        status = self.git("status", "--porcelain")
        code, output = self.run_main("--upstream-ref", "upstream", "--merge-base", "base", "--json")
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertFalse(report["clean"])
        self.assertEqual(report["conflicted_files"], ["apps/api/x.py"])
        self.assertEqual(report["by_kind"], {"content": ["apps/api/x.py"]})
        self.assertEqual(report["by_area"], {"apps/api": ["apps/api/x.py"]})
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("for-each-ref"), refs)
        self.assertEqual(self.git("status", "--porcelain"), status)

    def test_merging_from_the_upstream_tip_itself_is_clean(self):
        code, output = self.run_main("--upstream-ref", "upstream", "--merge-base", "upstream", "--ours", "upstream")
        self.assertEqual(code, 0)
        self.assertIn("No conflicts.", output)

    def test_unknown_reference_is_an_error_not_an_option(self):
        code, _ = self.run_main("--upstream-ref=--output=x", "--merge-base", "base")
        self.assertEqual(code, 2)
        code, _ = self.run_main("--upstream-ref", "v9.9.9", "--merge-base", "base")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
