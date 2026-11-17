# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Behaviour of the host-side deployment scripts that the other suites do not cover.

The Swarm menu offers "7) Exit" and must accept it, and the scripts an operator
runs on a host must find bash through PATH, because /bin/bash does not exist on
NixOS and other non-FHS systems (upstream makeplane/plane#10264, #10030).
"""

import re
import subprocess
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SWARM = REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh"

# Scripts run on an operator's or developer's host. Container entrypoints keep
# /bin/bash: they run inside Hangar's own images, where it exists.
HOST_SCRIPTS = (
    "setup.sh",
    "apps/api/run_tests.sh",
    "deployments/aio/community/build.sh",
    "deployments/cli/community/install.sh",
    "deployments/cli/community/migrate-object-storage.sh",
    "deployments/cli/community/migration-0.13-0.14.sh",
    "deployments/cli/community/restore.sh",
    "deployments/swarm/community/swarm.sh",
)


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


class HostScriptShebangTests(unittest.TestCase):
    def test_host_scripts_find_bash_through_path(self):
        for path in HOST_SCRIPTS:
            with self.subTest(script=path):
                source = (REPOSITORY_ROOT / path).read_text()
                self.assertEqual(source.splitlines()[0], "#!/usr/bin/env bash")
                self.assertNotIn("/bin/bash -c", source)

    def test_every_host_script_is_listed(self):
        """A new host script under deployments/ must choose its shebang on purpose."""
        listed = set(HOST_SCRIPTS)
        found = {
            str(path.relative_to(REPOSITORY_ROOT))
            for path in (REPOSITORY_ROOT / "deployments").rglob("*.sh")
            # start.sh is the all-in-one image's entrypoint, not a host script.
            if path.name != "start.sh"
        }
        self.assertEqual(found - listed, set())


if __name__ == "__main__":
    unittest.main()
