# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The Kubernetes guide must name the release that is about to be tagged.

`build-branch.yml` greps `docs/kubernetes/README.md` for several literal strings
naming the release and refuses the publication when any is missing. That step
runs *after* the tag is pushed, and a pushed tag consumes its version: the
recovery from a failure there is a new release number, not a retry. rc.56 was
prepared twice without touching that file and came within one command of being
spent on the mistake.

Nothing about that check needs a tag to exist. The release version is the highest
`docs/releases/hangar-v*.md` present, which is exactly what the tag will be, so
the same assertions can run on every pull request that adds release notes -- back
where a missing line costs an edit rather than a version.

The assertions are read out of the workflow rather than copied here. A copy would
drift the first time someone adds a row to that table, and would then be checking
something the release no longer requires.
"""

import re
from pathlib import Path
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPOSITORY_ROOT / ".github" / "workflows" / "build-branch.yml"
DOCUMENTATION_PATH = REPOSITORY_ROOT / "docs" / "kubernetes" / "README.md"
NOTES_DIRECTORY = REPOSITORY_ROOT / "docs" / "releases"

_NOTES_NAME = re.compile(r"^hangar-v(.+)\.md$")
_REQUIRE_LITERAL = re.compile(r'require_literal "(.+)"\s*$', re.MULTILINE)


def version_sort_key(version):
    """Sort "0.1.0-rc.9" below "0.1.0-rc.10", which a string sort does not."""
    return [int(part) if part.isdigit() else part for part in re.split(r"[.-]", version)]


def released_versions():
    return sorted(
        (match.group(1) for match in (_NOTES_NAME.match(path.name) for path in NOTES_DIRECTORY.iterdir()) if match),
        key=version_sort_key,
    )


def workflow_literals(chart_version, version, git_tag):
    """The literals the publish workflow will look for, as it will look for them."""
    literals = []
    for raw in _REQUIRE_LITERAL.findall(WORKFLOW_PATH.read_text(encoding="utf-8")):
        literal = raw.replace("\\`", "`")
        literal = literal.replace("$chart_version", chart_version)
        literal = literal.replace("$VERSION", version)
        literal = literal.replace("$GIT_TAG", git_tag)
        literals.append(literal)
    return literals


class KubernetesReleaseDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.versions = released_versions()
        cls.chart_version = cls.versions[-1] if cls.versions else ""
        cls.version = f"v{cls.chart_version}"
        cls.git_tag = f"hangar-{cls.version}"
        cls.documentation = DOCUMENTATION_PATH.read_text(encoding="utf-8")

    def test_release_notes_exist_to_check_against(self):
        """A wrong notes directory would make every assertion below vacuous."""
        self.assertTrue(self.versions, f"No hangar-v*.md release notes under {NOTES_DIRECTORY}")

    def test_the_workflow_still_declares_literals_to_check(self):
        """If the publish step stops using require_literal, this test is checking nothing."""
        literals = workflow_literals(self.chart_version, self.version, self.git_tag)
        self.assertTrue(
            literals,
            f"No require_literal assertions found in {WORKFLOW_PATH.name}; this test no longer mirrors the release.",
        )

    def test_the_kubernetes_guide_names_the_release_about_to_be_tagged(self):
        missing = [
            literal
            for literal in workflow_literals(self.chart_version, self.version, self.git_tag)
            if literal not in self.documentation
        ]

        self.assertEqual(
            missing,
            [],
            "docs/kubernetes/README.md does not name "
            f"{self.git_tag}, so publishing that tag would fail after the tag is already spent. "
            f"Missing: {missing}",
        )

    def test_the_guide_does_not_still_point_at_the_previous_release(self):
        """The version strings above can be right while the notes link is stale."""
        if len(self.versions) < 2:
            self.skipTest("Only one release recorded")
        previous = self.versions[-2]
        stale_link = f"- [Release `v{previous}` notes](../releases/hangar-v{previous}.md)"
        self.assertNotIn(
            stale_link,
            self.documentation,
            f"The documentation index still links release notes for {previous} rather than {self.chart_version}.",
        )


if __name__ == "__main__":
    unittest.main()
