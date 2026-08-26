# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Every God Mode page defined in the menu has to appear in it.

The definitions and the rendered list live in two files. Adding a page to the
first and forgetting the second leaves it reachable only by typing its URL,
which is how the Branding page shipped in rc.31 — present, routed, working, and
invisible.
"""

import re
from pathlib import Path
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MENU_DIR = REPOSITORY_ROOT / "apps" / "admin" / "hooks" / "use-sidebar-menu"


class AdminSidebarMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = (MENU_DIR / "core.ts").read_text(encoding="utf-8")
        cls.rendered = (MENU_DIR / "index.ts").read_text(encoding="utf-8")

    def test_every_defined_entry_is_rendered(self):
        defined = set(re.findall(r"^  ([a-zA-Z]+): \{$", self.definitions, re.M))
        rendered = set(re.findall(r"coreSidebarMenuLinks\.([a-zA-Z]+)", self.rendered))

        self.assertTrue(defined, "no menu entries found; the parser is looking at the wrong shape")
        self.assertEqual(
            defined - rendered,
            set(),
            "these God Mode pages are defined but never shown, so they are reachable "
            f"only by URL: {sorted(defined - rendered)}",
        )

    def test_every_rendered_entry_is_defined(self):
        defined = set(re.findall(r"^  ([a-zA-Z]+): \{$", self.definitions, re.M))
        rendered = set(re.findall(r"coreSidebarMenuLinks\.([a-zA-Z]+)", self.rendered))

        self.assertEqual(rendered - defined, set())


if __name__ == "__main__":
    unittest.main()
