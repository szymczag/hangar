# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Security settings the fork depends on (FORK.md, "Security invariants", S13).

The module-level defaults are read in a fresh interpreter, because the settings
under test are evaluated once at import and the test settings override some of
them.
"""

import json
import os
import subprocess
import sys

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from plane.settings import common

pytestmark = pytest.mark.unit


def _fresh_settings(names, **environment):
    """Import plane.settings.common in a new interpreter and return some values."""
    env = {key: value for key, value in os.environ.items() if key not in environment}
    env.update({key: value for key, value in environment.items() if value is not None})
    script = (
        "import json, plane.settings.common as c; "
        f"print(json.dumps({{n: getattr(c, n) for n in {list(names)!r}}}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=os.path.dirname(common.BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


class TestMiddleware:
    def test_content_security_policy_middleware_is_installed(self):
        assert "plane.middleware.content_security_policy.ContentSecurityPolicyMiddleware" in common.MIDDLEWARE
        assert "plane.middleware.content_security_policy.ContentSecurityPolicyMiddleware" in settings.MIDDLEWARE


class TestSecretKey:
    def test_published_values_are_flagged(self):
        assert {
            "60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5",
            "change-this-key-on-deployment",
        } <= common._INSECURE_SECRET_KEYS

    def test_an_empty_key_falls_back_to_a_random_one(self):
        first = _fresh_settings(["SECRET_KEY"], SECRET_KEY="")["SECRET_KEY"]
        second = _fresh_settings(["SECRET_KEY"], SECRET_KEY="")["SECRET_KEY"]
        assert first and second and first != second
        assert first not in common._INSECURE_SECRET_KEYS


class TestAdminWebAuthnDefault:
    def test_second_factor_is_required_unless_the_operator_turns_it_off(self):
        assert _fresh_settings(["ADMIN_WEBAUTHN_REQUIRED"], ADMIN_WEBAUTHN_REQUIRED=None) == {
            "ADMIN_WEBAUTHN_REQUIRED": True
        }
        assert _fresh_settings(["ADMIN_WEBAUTHN_REQUIRED"], ADMIN_WEBAUTHN_REQUIRED="0") == {
            "ADMIN_WEBAUTHN_REQUIRED": False
        }


class TestValidators:
    @pytest.mark.parametrize("value", ["10/minute", "1/second", "300/hour", "5/day"])
    def test_rate_accepts_drf_syntax(self, monkeypatch, value):
        monkeypatch.setenv("HANGAR_TEST_RATE", value)
        assert common._rate_setting("HANGAR_TEST_RATE", "10/minute") == value

    @pytest.mark.parametrize("value", ["0/minute", "10/fortnight", "", "10", "-1/minute", "10/minute;"])
    def test_rate_refuses_anything_else(self, monkeypatch, value):
        monkeypatch.setenv("HANGAR_TEST_RATE", value)
        with pytest.raises(ImproperlyConfigured):
            common._rate_setting("HANGAR_TEST_RATE", "10/minute")

    def test_bounded_integer_accepts_the_range(self, monkeypatch):
        monkeypatch.setenv("HANGAR_TEST_INT", "5")
        assert common._bounded_integer_setting("HANGAR_TEST_INT", 1, 1, 10) == 5
        monkeypatch.delenv("HANGAR_TEST_INT")
        assert common._bounded_integer_setting("HANGAR_TEST_INT", 3, 1, 10) == 3

    @pytest.mark.parametrize("value", ["0", "11", "five", "", "1e3"])
    def test_bounded_integer_refuses_out_of_range_or_non_integer(self, monkeypatch, value):
        monkeypatch.setenv("HANGAR_TEST_INT", value)
        with pytest.raises(ImproperlyConfigured):
            common._bounded_integer_setting("HANGAR_TEST_INT", 1, 1, 10)

    @pytest.mark.parametrize(
        "name,value",
        [("CALENDAR_CAPACITY_USER_RATE", "unlimited"), ("CAPACITY_MAX_ACTIVE_HOLDS_PER_USER", "100000")],
    )
    def test_a_malformed_value_stops_the_settings_from_loading(self, name, value):
        with pytest.raises(subprocess.CalledProcessError) as raised:
            _fresh_settings([name], **{name: value})
        assert "ImproperlyConfigured" in raised.value.stderr
