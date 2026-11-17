# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Behaviour of the host-side deployment scripts that the other suites do not cover.

The Swarm menu offers "7) Exit" and must accept it (upstream
makeplane/plane#10264).
"""

import re
import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SWARM = REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh"


def _function(source: str, name: str) -> str:
    match = re.search(rf"^function {name}\(\)\s*\{{.*?^}}$", source, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"no {name}()")
    return match.group(0)


class SwarmMenuTests(unittest.TestCase):
    def _choose(self, choice: str) -> subprocess.CompletedProcess:
        stubs = "".join(
            f"function {name}() {{ echo {name.upper()}; }}\n"
            for name in ("deployStack", "removeStack", "viewStatus", "redeployStack", "upgrade", "viewLogs")
        )
        program = _function(SWARM.read_text(), "askForAction") + "\n" + stubs + "askForAction\necho RETURNED\n"
        return subprocess.run(
            ["bash", "-c", program], input=choice, capture_output=True, text=True, timeout=10
        )

    def test_exit_is_accepted(self):
        result = self._choose("7\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("invalid selection", result.stdout)
        self.assertNotIn("VIEWSTATUS", result.stdout)
        self.assertNotIn("RETURNED", result.stdout)

    def test_every_listed_action_is_accepted(self):
        for choice, expected in (("1", "DEPLOYSTACK"), ("6", "VIEWLOGS")):
            with self.subTest(choice=choice):
                result = self._choose(choice + "\n")
                self.assertNotIn("invalid selection", result.stdout)
                self.assertIn(expected, result.stdout)

    def test_an_unlisted_action_is_still_refused(self):
        result = self._choose("8\n")
        self.assertIn("8: invalid selection.", result.stdout)


if __name__ == "__main__":
    unittest.main()
