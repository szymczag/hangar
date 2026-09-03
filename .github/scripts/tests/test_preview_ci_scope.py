# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "api-tests.yml"
WEB_WORKFLOW = (
    REPOSITORY_ROOT
    / ".github"
    / "workflows"
    / "pull-request-build-lint-web-apps.yml"
)


class PreviewCiScopeTests(unittest.TestCase):
    def test_preview_pushes_scope_api_tests_to_the_pushed_range(self):
        workflow = API_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("BEFORE_SHA: ${{ github.event.before }}", workflow)
        self.assertIn('changed=$(git diff --name-only "$BEFORE_SHA" "$COMMIT_SHA")', workflow)
        self.assertIn('[[ "$BEFORE_SHA" =~ ^0{40}$ ]]', workflow)
        self.assertIn('echo "api=true" >> "$GITHUB_OUTPUT"', workflow)

    def test_preview_pushes_use_turbo_affected_for_web_checks(self):
        workflow = WEB_WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(workflow.count('= "workflow_dispatch"'), 4)
        for command in ("check:format", "build", "check:lint", "check:types"):
            self.assertIn(f"pnpm turbo run {command} --affected", workflow)


if __name__ == "__main__":
    unittest.main()
