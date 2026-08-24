# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The Compose asset must pass through the settings a deployment has to reach.

`x-app-env` in the published `docker-compose.yml` is the entire environment the
API containers receive — there is no `env_file` — so a variable an operator sets
in `variables.env` and that nothing forwards is silently ignored. That is how
`ADMIN_WEBAUTHN_REQUIRED` shipped in rc.30 unreachable: the documented way to
recover a console nobody can sign in to could not be set on Compose or Swarm,
which downloads the same file.

These tests compare the settings module against the asset, so a new
operator-facing variable cannot be added on one side alone.
"""

import re
from pathlib import Path
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "docker-compose.yml"
VARIABLES_PATH = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "variables.env"
SETTINGS_PATH = REPOSITORY_ROOT / "apps" / "api" / "plane" / "settings" / "common.py"

# Prefixes whose settings configure how administrators reach the console. A
# deployment that cannot set these cannot be recovered from the outside.
CONSOLE_PREFIXES = ("WEBAUTHN_", "ADMIN_2FA_", "ADMIN_WEBAUTHN_")

_ENV_READ = re.compile(r"os\.environ\.get\(\s*\"([A-Z0-9_]+)\"")


class ComposeEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = COMPOSE_PATH.read_text(encoding="utf-8")
        cls.variables = VARIABLES_PATH.read_text(encoding="utf-8")
        cls.settings = SETTINGS_PATH.read_text(encoding="utf-8")

    def console_settings(self):
        return sorted(
            {
                name
                for name in _ENV_READ.findall(self.settings)
                if name.startswith(CONSOLE_PREFIXES)
            }
        )

    def test_the_settings_that_gate_console_access_are_forwarded(self):
        missing = [name for name in self.console_settings() if f"  {name}:" not in self.compose]

        self.assertEqual(
            missing,
            [],
            "docker-compose.yml does not forward these to the API containers, so setting "
            f"them has no effect: {missing}",
        )

    def test_the_recovery_switch_is_documented_where_an_operator_looks(self):
        """An escape hatch nobody knows about is not an escape hatch."""
        self.assertIn("ADMIN_WEBAUTHN_REQUIRED=", self.variables)

    def test_compose_has_no_env_file_that_would_make_this_check_moot(self):
        """If this ever fails, the tests above are checking the wrong thing.

        A service reading variables.env wholesale would forward everything, and
        an explicit list would no longer be the contract.
        """
        self.assertNotIn("env_file", self.compose)


if __name__ == "__main__":
    unittest.main()
