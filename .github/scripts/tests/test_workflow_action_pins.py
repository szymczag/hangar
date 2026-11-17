# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIRECTORY = REPOSITORY_ROOT / ".github" / "workflows"
USES_PATTERN = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<value>.*?)\s*$", re.M)
PINNED_PATTERN = re.compile(
    r"^(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)@(?P<sha>[0-9a-f]{40})"
    r" # (?P<version>v\d+\.\d+\.\d+)$"
)
DOCKER_PATTERN = re.compile(r"^docker://\S+@sha256:[0-9a-f]{64}(?: # \S+)?$")


def workflow_files():
    return sorted(
        path
        for pattern in ("*.yml", "*.yaml")
        for path in WORKFLOWS_DIRECTORY.glob(pattern)
    )


def workflow_uses(path):
    return [match["value"] for match in USES_PATTERN.finditer(path.read_text(encoding="utf-8"))]


class WorkflowActionPinTests(unittest.TestCase):
    def test_workflows_are_discovered(self):
        self.assertTrue(workflow_files())

    def test_every_action_is_local_or_pinned_to_a_commit_with_a_version(self):
        for path in workflow_files():
            for use in workflow_uses(path):
                with self.subTest(workflow=path.name, uses=use):
                    if use.startswith("./"):
                        continue
                    if use.startswith("docker://"):
                        self.assertRegex(use, DOCKER_PATTERN)
                        continue
                    self.assertRegex(use, PINNED_PATTERN)

    def test_each_commit_carries_one_version(self):
        versions = {}
        for path in workflow_files():
            for use in workflow_uses(path):
                match = PINNED_PATTERN.match(use)
                if match is None:
                    continue
                repository = "/".join(match["action"].split("/")[:2])
                key = (repository, match["sha"])
                with self.subTest(workflow=path.name, uses=use):
                    self.assertEqual(versions.setdefault(key, match["version"]), match["version"])

    def test_pattern_rejects_floating_and_uncommented_references(self):
        for use in (
            "actions/checkout@v6",
            "actions/checkout@main",
            "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10",
            "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6",
            "actions/checkout@df4cb1c # v6.0.3",
        ):
            with self.subTest(uses=use):
                self.assertIsNone(PINNED_PATTERN.match(use))
        self.assertIsNotNone(
            PINNED_PATTERN.match(
                "github/codeql-action/init@33d7b85da1a04171e211befe2c739303b9a4c066 # v4.39.3"
            )
        )


if __name__ == "__main__":
    unittest.main()
