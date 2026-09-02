# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Operator-authored branding text is held to the same rule as everything else.

These four fields had no length cap and no character validation at all. That
matters most for the support text, which is rendered on the pages shown when the
instance cannot be reached: a bidirectional override there reorders the sentence
telling somebody how to get help, at the moment nothing else works, and escaping
downstream does not help because the characters are not markup.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import User
from plane.license.models import InstanceAdmin, InstanceConfiguration
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin

setup_instance = _google_auth.setup_instance

URL = "/api/instances/configurations/"

CAPS = {
    "INSTANCE_BRANDING_NAME": 100,
    "INSTANCE_SIGN_IN_HEADER": 120,
    "INSTANCE_SIGN_IN_SUBHEADER": 300,
    "INSTANCE_SUPPORT_TEXT": 300,
}


def _seed(key):
    """The suite runs with --nomigrations, so the stored row is arranged here.

    The endpoint updates existing configuration rows rather than creating them,
    so an accepted write needs a row to land in. The rejection cases below need
    no seed, because validation runs before the lookup -- which is the order it
    should be in.
    """
    InstanceConfiguration.objects.update_or_create(
        key=key, defaults={"value": "", "category": "BRANDING", "is_encrypted": False}
    )


@pytest.fixture
def admin_client(db, setup_instance):
    for key in CAPS:
        _seed(key)
    _seed("INSTANCE_ACCENT_COLOR")
    admin = User.objects.create(email="admin@ops.example", username=uuid.uuid4().hex)
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    return client


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(CAPS))
def test_ordinary_wording_is_accepted(admin_client, key):
    response = admin_client.patch(URL, {key: "Contact the IT service desk on extension 4200."}, format="json")

    assert response.status_code == 200, response.content


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("key,cap", sorted(CAPS.items()))
def test_text_beyond_the_cap_is_refused(admin_client, key, cap):
    response = admin_client.patch(URL, {key: "x" * (cap + 1)}, format="json")

    assert response.status_code == 400
    assert str(cap) in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(CAPS))
def test_a_bidirectional_override_is_refused(admin_client, key):
    response = admin_client.patch(URL, {key: "Call the service desk‮"}, format="json")

    assert response.status_code == 400
    assert "control or formatting characters" in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("key", sorted(CAPS))
def test_a_line_break_is_refused(admin_client, key):
    response = admin_client.patch(URL, {key: "First line\nSecond line"}, format="json")

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_clearing_the_text_is_still_allowed(admin_client):
    """Empty means "use the built-in wording", and must stay reachable."""
    response = admin_client.patch(URL, {"INSTANCE_SUPPORT_TEXT": ""}, format="json")

    assert response.status_code == 200, response.content


@pytest.mark.contract
@pytest.mark.django_db
def test_the_colour_rule_is_untouched(admin_client):
    """The neighbouring validation must keep working."""
    assert admin_client.patch(URL, {"INSTANCE_ACCENT_COLOR": "#1d4ed8"}, format="json").status_code == 200
    assert admin_client.patch(URL, {"INSTANCE_ACCENT_COLOR": "red"}, format="json").status_code == 400
