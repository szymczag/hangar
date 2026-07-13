# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "build-branch.yml"


class ReleaseWorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_only_namespaced_release_tags_trigger_publication(self):
        self.assertIn('      - "hangar-v[0-9]+.[0-9]+.[0-9]+"', self.workflow)
        self.assertIn('      - "hangar-v[0-9]+.[0-9]+.[0-9]+-*"', self.workflow)
        self.assertNotIn('      - "v[0-9]+.[0-9]+.[0-9]+"', self.workflow)
        self.assertNotIn('      - "v[0-9]+.[0-9]+.[0-9]+-*"', self.workflow)

    def test_workflow_consumes_validated_metadata(self):
        self.assertIn("python3 .github/scripts/release_metadata.py", self.workflow)
        self.assertIn("--format github-output", self.workflow)
        self.assertIn("Require release commit on preview", self.workflow)
        self.assertIn("Require a verified annotated release tag", self.workflow)
        self.assertIn("Signed tag name does not match the pushed release ref", self.workflow)

    def test_immutable_tag_checks_fail_closed(self):
        self.assertIn("Log in to GHCR for immutable-tag checks", self.workflow)
        self.assertIn("Could not prove that immutable image tag is unused", self.workflow)
        self.assertIn("GitHub Release immutability check failed", self.workflow)

    def test_github_release_uses_the_git_tag_not_the_product_version(self):
        self.assertIn('gh release create "$GIT_TAG"', self.workflow)
        self.assertIn("--verify-tag", self.workflow)
        self.assertNotIn('gh release create "$VERSION"', self.workflow)
        self.assertNotIn("--generate-notes", self.workflow)

    def test_release_images_include_upstream_provenance(self):
        repository_label = (
            "io.github.szymczag.hangar.upstream.repository="
            "${{ needs.setup.outputs.upstream_repository }}"
        )
        revision_label = (
            "io.github.szymczag.hangar.upstream.revision="
            "${{ needs.setup.outputs.upstream_revision }}"
        )
        self.assertEqual(self.workflow.count(repository_label), 2)
        self.assertEqual(self.workflow.count(revision_label), 2)

    def test_stable_promotion_happens_after_release_creation(self):
        release_position = self.workflow.index("gh release create")
        promotion_position = self.workflow.index("docker buildx imagetools create")
        self.assertLess(release_position, promotion_position)


if __name__ == "__main__":
    unittest.main()
