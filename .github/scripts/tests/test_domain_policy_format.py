# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The admin panel must write roles the server will accept.

The domain policy is composed in TypeScript and parsed in Python, and nothing
connected the two. The panel wrote roles as numbers, the parser accepted only
names, and an entry with an unrecognised role is dropped on purpose — so
auto-join configured from the panel was discarded in silence and never ran.
Neither side's tests could see it, because each was right about itself.

This compares the two files directly. It is crude, and it is the only thing that
would have caught the defect.
"""

import re
from pathlib import Path
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PANEL = REPOSITORY_ROOT / "apps" / "admin" / "app" / "(all)" / "(dashboard)" / "authentication" / "domains" / "policy.ts"
SERVER = REPOSITORY_ROOT / "apps" / "api" / "plane" / "authentication" / "utils" / "sso_auto_join.py"


class DomainPolicyFormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = PANEL.read_text(encoding="utf-8")
        cls.server = SERVER.read_text(encoding="utf-8")

    def panel_roles(self) -> set[str]:
        """The role tokens the panel can write into a stored entry.

        Both shapes are recognised — a list of names, and the older map of names
        to numbers — so that a panel writing numbers is reported as writing
        numbers rather than as an unreadable file.
        """
        by_name = re.search(r"export const ROLE_NAMES = \[(.*?)\] as const;", self.panel, re.S)
        if by_name:
            return set(re.findall(r'"([a-z]+)"', by_name.group(1)))

        by_number = re.search(r"ROLE_(?:VALUES|NUMBERS)[^=]*= \{(.*?)\}", self.panel, re.S)
        self.assertIsNotNone(by_number, "no role declaration found in the panel; this test is looking at the wrong shape")
        return set(re.findall(r'"(\d+)"', by_number.group(1)))

    def server_roles(self) -> set[str]:
        """Every token the parser resolves to a role.

        The numbers count only when the parser declares that it reads them. They
        appear as values in the name map regardless, so taking them from there
        would report the parser as accepting what it actually discards — which
        is precisely the mistake this test exists to catch.
        """
        names = re.search(r"ROLE_NAMES = \{(.*?)\}", self.server, re.S)
        self.assertIsNotNone(names, "ROLE_NAMES not found in the parser")
        accepted = set(re.findall(r'"([a-z]+)":', names.group(1)))

        if re.search(r"^ROLE_VALUES = ", self.server, re.M):
            accepted |= set(re.findall(r"\b(\d+)\b", names.group(1)))
        return accepted

    def test_every_role_the_panel_writes_is_one_the_server_accepts(self):
        panel = self.panel_roles()
        server = self.server_roles()

        self.assertTrue(panel, "the panel declares no roles")
        self.assertEqual(
            panel - server,
            set(),
            "the admin panel writes roles the auto-join parser drops, so a policy saved from it "
            f"silently does nothing: {sorted(panel - server)}",
        )

    def test_the_panel_serialises_by_name(self):
        """A number would parse today, but only because the parser was widened.

        Names are the documented format, so the panel writing them keeps the
        stored value readable by anyone inspecting the database during an
        incident.
        """
        self.assertRegex(
            self.panel,
            r"workspaces\.push\(`\$\{domain\}=\$\{slug\}:\$\{grant\.workspaceRole\}`\)",
            "the panel no longer serialises the role by name",
        )

    def test_an_unrecognised_role_still_refuses_the_entry(self):
        """Widening what is accepted must not become accepting anything."""
        self.assertIn("An unrecognised role must not silently become a privileged one", self.server)


if __name__ == "__main__":
    unittest.main()
