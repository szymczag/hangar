# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Every authentication error the API can return must say something.

The API decides an outcome and hands the browser a number. The web app turns
that number into a message through two lookups, and a code missing from either
renders nothing at all: `authErrorHandler` returns undefined, no banner is
shown, and the person is bounced back to the sign-in page with only the number
in the URL. The "Something went wrong." fallback does not save it, because the
banner list gates the fallback too.

Six fork-added codes shipped that way, `SSO_ACCOUNT_LINK_REQUIRED` among them:
the API refused the sign-in for a reason an administrator could act on, and the
person was told nothing.
"""

import re
from pathlib import Path
import unittest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_CODES = REPOSITORY_ROOT / "apps" / "api" / "plane" / "authentication" / "adapter" / "error.py"
WEB_HELPER = REPOSITORY_ROOT / "apps" / "web" / "helpers" / "authentication.helper.tsx"

# Codes the sign-in page never receives, because the God Mode console answers
# them on its own screens. Listing one here is a claim that nobody can hit it
# while signing in to the application.
CONSOLE_ONLY_PREFIXES = ("ADMIN_",)


class AuthErrorMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = API_CODES.read_text(encoding="utf-8")
        cls.web = WEB_HELPER.read_text(encoding="utf-8")

    def api_codes(self) -> dict[str, str]:
        """Number to name, as the API defines them."""
        return {
            number: name
            for name, number in re.findall(r'"([A-Z_0-9]+)":\s*(\d+)', self.api)
            if not name.startswith(CONSOLE_ONLY_PREFIXES)
        }

    def web_codes(self) -> dict[str, str]:
        """Number to name, as the web app knows them.

        Keyed by number rather than by name deliberately: the number is what
        crosses the wire, and the two sides spell several of them differently.
        """
        return {number: name for name, number in re.findall(r'([A-Z_0-9]+) = "(\d+)"', self.web)}

    def test_every_api_code_the_browser_can_receive_is_known_to_the_web_app(self):
        api = self.api_codes()
        web = self.web_codes()
        self.assertTrue(api, "no error codes found; this test is looking at the wrong shape")

        missing = sorted(f"{number} ({name})" for number, name in api.items() if number not in web)

        self.assertEqual(
            missing,
            [],
            "the API can return these and the web app has no message for them, so the sign-in "
            f"page shows nothing at all: {missing}",
        )

    def test_every_known_code_has_a_message(self):
        without_message = sorted(
            name for name in self.web_codes().values() if f"EAuthenticationErrorCodes.{name}]:" not in self.web
        )

        self.assertEqual(
            without_message,
            [],
            f"declared but with no message, so they render as nothing: {without_message}",
        )


if __name__ == "__main__":
    unittest.main()
