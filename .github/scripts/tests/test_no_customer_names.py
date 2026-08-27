# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""No deploying organisation's name may appear in this repository.

Hangar is published source. A customer's name in a fixture, placeholder or
comment tells every reader of the repository who runs it, and the repository
outlives the reason it was convenient — a diagnosis pasted from a live instance,
a slug copied into a test because it was the one in front of whoever wrote it.

This has now happened twice: once as a placeholder in the God Mode branding form,
and once as a workspace slug in an onboarding test, taken from a production
report. Both were removed by hand. A rule that depends on remembering is not a
rule, so this checks.

The forbidden terms are stored encoded, because a test written the obvious way
would itself put the name in the repository it is meant to keep it out of. Add a
term with `base64.b64encode(b"name").decode()`.
"""

import base64
from pathlib import Path
import subprocess
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

# Organisations that deploy Hangar. Encoded; see the module docstring.
FORBIDDEN_TERMS_B64 = ("c2VjdXJpdHVt",)

# Nothing is exempt on the grounds of being "only a test" or "only a comment" —
# that is exactly how both occurrences got in. Only paths git does not track are
# out of scope, since they are not published.


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=True,
    )
    return [name for name in result.stdout.decode("utf-8", "replace").split("\0") if name]


class CustomerNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.terms = [base64.b64decode(term).decode("utf-8") for term in FORBIDDEN_TERMS_B64]
        cls.files = _tracked_files()

    def test_the_check_has_something_to_look_for(self):
        self.assertTrue(self.terms, "no forbidden terms configured; this test would pass on anything")
        self.assertTrue(self.files, "no tracked files found; this test is looking at the wrong place")

    def test_no_tracked_file_names_a_deploying_organisation(self):
        offenders = []
        for name in self.files:
            path = REPOSITORY_ROOT / name
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
            except (OSError, UnicodeDecodeError):
                continue
            for term in self.terms:
                if term in content or term in name.lower():
                    offenders.append(f"{name}: {term!r}")

        self.assertEqual(
            offenders,
            [],
            "a deploying organisation is named in published source, which tells every reader "
            f"of this repository who runs it: {offenders}",
        )


if __name__ == "__main__":
    unittest.main()
