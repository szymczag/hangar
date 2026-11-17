# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""God Mode settings must survive the installer replacing a template SECRET_KEY.

Settings saved in God Mode (the SMTP password, OAuth client secrets) are
encrypted with a key derived from SECRET_KEY. The installers now replace the
published template SECRET_KEY on upgrade, and the API refuses to start with it,
so without re-encryption those settings would silently decrypt to nothing
after the upgrade: mail would stop and sign-in providers would break.
"""

import pytest
from django.conf import settings
from django.test import override_settings

from plane.license.management.commands.configure_instance import Command
from plane.license.models import InstanceConfiguration
from plane.license.utils.encryption import decrypt_data, encrypt_data, reencrypt_from_legacy_key

TEMPLATE_KEY = "change-this-key-on-deployment"
NEW_KEY = "a-new-random-secret-key-for-the-unit-test-0123456789"


def _encrypted_under(key, value):
    with override_settings(SECRET_KEY=key):
        return encrypt_data(value)


@pytest.mark.unit
def test_the_template_keys_are_the_legacy_keys():
    assert TEMPLATE_KEY in settings.LEGACY_SECRET_KEYS
    assert "60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5" in settings.LEGACY_SECRET_KEYS


@pytest.mark.unit
@override_settings(SECRET_KEY=NEW_KEY)
def test_a_value_encrypted_under_a_template_key_moves_to_the_current_key():
    stored = _encrypted_under(TEMPLATE_KEY, "smtp-password")
    assert decrypt_data(stored) == ""

    moved = reencrypt_from_legacy_key(stored)

    assert moved is not None
    assert decrypt_data(moved) == "smtp-password"


@pytest.mark.unit
@override_settings(SECRET_KEY=NEW_KEY)
def test_values_under_the_current_key_or_an_unknown_key_are_left_alone():
    assert reencrypt_from_legacy_key(encrypt_data("current")) is None
    assert reencrypt_from_legacy_key(_encrypted_under("some-other-operator-key", "lost")) is None
    assert reencrypt_from_legacy_key("") is None
    assert reencrypt_from_legacy_key(None) is None


@pytest.mark.unit
@override_settings(SECRET_KEY=TEMPLATE_KEY)
def test_nothing_changes_while_the_template_key_is_still_in_use():
    assert reencrypt_from_legacy_key(encrypt_data("value")) is None


@pytest.mark.django_db
@override_settings(SECRET_KEY=NEW_KEY)
def test_configure_instance_re_encrypts_stored_settings(capsys):
    legacy = InstanceConfiguration.objects.create(
        key="HANGAR_TEST_LEGACY_SECRET",
        value=_encrypted_under(TEMPLATE_KEY, "client-secret"),
        category="TEST",
        is_encrypted=True,
    )
    current = InstanceConfiguration.objects.create(
        key="HANGAR_TEST_CURRENT_SECRET",
        value=encrypt_data("already-current"),
        category="TEST",
        is_encrypted=True,
    )
    plain = InstanceConfiguration.objects.create(
        key="HANGAR_TEST_PLAIN", value="not-encrypted", category="TEST", is_encrypted=False
    )
    current_value = current.value

    Command().reencrypt_legacy_values()

    legacy.refresh_from_db()
    current.refresh_from_db()
    plain.refresh_from_db()
    assert decrypt_data(legacy.value) == "client-secret"
    assert current.value == current_value
    assert plain.value == "not-encrypted"
    assert "HANGAR_TEST_LEGACY_SECRET re-encrypted" in capsys.readouterr().out
