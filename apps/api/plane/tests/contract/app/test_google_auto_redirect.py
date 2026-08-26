# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from plane.db.models import User
from plane.license.models import InstanceAdmin, InstanceConfiguration
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin

setup_instance = _google_auth.setup_instance


def _seed(value="0"):
    return InstanceConfiguration.objects.update_or_create(
        key="GOOGLE_AUTO_REDIRECT",
        defaults={"value": value, "category": "GOOGLE", "is_encrypted": False},
    )[0]


@pytest.fixture
def admin_client(db, setup_instance):
    admin = User.objects.create(email="admin@ops.example", username=uuid.uuid4().hex)
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    return client


@pytest.mark.contract
@pytest.mark.django_db
def test_google_auto_redirect_is_disabled_by_default(db, setup_instance):
    cache.clear()

    response = APIClient().get("/api/instances/")

    assert response.status_code == 200
    assert response.data["config"]["is_google_auto_redirect_enabled"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_google_auto_redirect_can_be_enabled_by_an_instance_admin(admin_client):
    _seed()

    saved = admin_client.patch(
        "/api/instances/configurations/",
        {"GOOGLE_AUTO_REDIRECT": "1"},
        format="json",
    )

    assert saved.status_code == 200, saved.data
    cache.clear()
    config = APIClient().get("/api/instances/").data["config"]
    assert config["is_google_auto_redirect_enabled"] is True


@pytest.mark.contract
@pytest.mark.django_db
def test_app_sign_out_returns_with_auto_redirect_suppressed(db, setup_instance):
    response = APIClient().post("/auth/sign-out/")

    assert response.status_code == 302
    assert parse_qs(urlparse(response["Location"]).query) == {"signed_out": ["1"]}
