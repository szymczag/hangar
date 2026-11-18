# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""God Mode never reads a stored secret back (FORK.md, "Security invariants", S24).

The provider forms show whether a secret is configured, not what it is. That
holds only while every secret is stored encrypted and the configuration
endpoint blanks encrypted values, so both halves are pinned here through the
endpoint the admin app calls.
"""

import re
import uuid

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from plane.db.models import User
from plane.license.models import InstanceAdmin, InstanceConfiguration
from plane.license.utils.encryption import encrypt_data
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin
from plane.utils.instance_config_variables import instance_config_variables

setup_instance = _google_auth.setup_instance

URL = "/api/instances/configurations/"
SECRET_NAME = re.compile(r"(_SECRET|_PASSWORD|_API_KEY|_PRIVATE_KEY|_TOKEN)$")
# ENABLE_EMAIL_PASSWORD and the like are switches named after a secret, not secrets.
SECRET_KEYS = sorted(
    item["key"]
    for item in instance_config_variables
    if SECRET_NAME.search(item["key"]) and not item["key"].startswith(("ENABLE_", "IS_"))
)


def _marker(key):
    return f"stored-secret-{key.lower()}-{uuid.uuid4().hex}"


def test_the_secret_list_is_not_empty():
    # Guards the guard: a renamed variable list must not make the sweep vacuous.
    assert {"GOOGLE_CLIENT_SECRET", "OIDC_CLIENT_SECRET", "EMAIL_HOST_PASSWORD"} <= set(SECRET_KEYS)


@pytest.mark.parametrize("key", SECRET_KEYS)
def test_every_secret_is_declared_encrypted(key):
    definition = next(item for item in instance_config_variables if item["key"] == key)
    assert definition["is_encrypted"] is True


@pytest.fixture
def admin_client(db, setup_instance):
    cache.clear()
    admin = User.objects.create(email="admin@ops.example", username=uuid.uuid4().hex)
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    yield client
    cache.clear()


@pytest.mark.contract
@pytest.mark.django_db
def test_get_never_returns_a_stored_secret(admin_client):
    plaintext = {}
    for item in instance_config_variables:
        if item["key"] not in SECRET_KEYS:
            continue
        plaintext[item["key"]] = _marker(item["key"])
        InstanceConfiguration.objects.update_or_create(
            key=item["key"],
            defaults={
                "value": encrypt_data(plaintext[item["key"]]),
                "category": item["category"],
                "is_encrypted": item["is_encrypted"],
            },
        )

    response = admin_client.get(URL)

    assert response.status_code == 200
    body = response.content.decode()
    rows = {row["key"]: row for row in response.json()}
    for key, secret in plaintext.items():
        assert secret not in body, f"{key} was returned in clear"
        stored = InstanceConfiguration.objects.get(key=key).value
        assert stored not in body, f"{key} was returned in its encrypted form"
        if key in rows:
            assert rows[key]["value"] == ""
            assert rows[key]["is_configured"] is True


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unconfigured_secret_reads_as_unconfigured(admin_client):
    InstanceConfiguration.objects.update_or_create(
        key="GITHUB_CLIENT_SECRET",
        defaults={"value": "", "category": "GITHUB", "is_encrypted": True},
    )
    rows = {row["key"]: row for row in admin_client.get(URL).json()}
    assert rows["GITHUB_CLIENT_SECRET"]["value"] == ""
    assert rows["GITHUB_CLIENT_SECRET"]["is_configured"] is False
