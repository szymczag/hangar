# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What an instance tells a caller who has not signed in.

/api/instances/ is read by every sign-in page, so it answers without a
session. Without a verified console session it carries only what those pages
need; the instance's identity and version, the default workspace, integration
identifiers and internal URLs go to signed-in users through
/api/users/me/instance-config/ instead.
"""

import uuid
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import User, Workspace
from plane.license.api.views.instance import (
    ANONYMOUS_CONFIG_KEYS,
    ANONYMOUS_INSTANCE_KEYS,
    ANONYMOUS_PRODUCT_KEYS,
)
from plane.license.models import Instance, InstanceAdmin, InstanceConfiguration
from plane.tests.support.admin_session import authenticate_admin
from plane.utils.cache import generate_cache_key

INSTANCE_URL = "/api/instances/"
MEMBER_URL = "/api/users/me/instance-config/"

WITHHELD_CONFIG_KEYS = (
    "default_workspace_id",
    "posthog_api_key",
    "posthog_host",
    "slack_client_id",
    "github_app_name",
    "has_llm_configured",
    "api_token_minimum_role",
    "force_private_visibility",
    "file_size_limit",
    "admin_base_url",
    "space_base_url",
    "app_base_url",
    "instance_changelog_url",
    "is_self_managed",
    "provider_managed_profiles",
    "is_workspace_creation_disabled",
    "is_todoist_imports_enabled",
    "is_google_calendar_capacity_enabled",
)
WITHHELD_INSTANCE_KEYS = ("instance_id", "instance_name", "domain", "current_version", "latest_version", "namespace")


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def instance(db):
    return Instance.objects.create(
        instance_name="Corp Hangar",
        instance_id=str(uuid.uuid4()),
        current_version="0.1.0-rc.99",
        domain="hangar.corp.example",
        last_checked_at=timezone.now(),
        is_setup_done=True,
    )


@pytest.fixture
def default_workspace(db, instance):
    owner = User.objects.create(email=f"owner-{uuid.uuid4().hex[:6]}@corp.example", username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(name="Corp", owner=owner, slug=f"corp-{uuid.uuid4().hex[:6]}")
    InstanceConfiguration.objects.update_or_create(
        key="INSTANCE_DEFAULT_WORKSPACE_ID",
        defaults={"value": str(workspace.id), "category": "WORKSPACE", "is_encrypted": False},
    )
    return workspace


def _user(prefix):
    return User.objects.create(email=f"{prefix}-{uuid.uuid4().hex[:6]}@corp.example", username=uuid.uuid4().hex)


@pytest.mark.contract
@pytest.mark.django_db
class TestAnonymousInstancePayload:
    def test_only_sign_in_keys_are_served(self, instance, default_workspace):
        with patch.dict("os.environ", {"APP_VERSION": "0.1.0-rc.99", "POSTHOG_API_KEY": "phc_secret"}):
            data = APIClient().get(INSTANCE_URL).json()

        assert set(data) == {"config", "instance"}
        assert set(data["config"]) <= ANONYMOUS_CONFIG_KEYS | {"product"}
        assert set(data["config"]["product"]) <= ANONYMOUS_PRODUCT_KEYS
        assert set(data["instance"]) <= ANONYMOUS_INSTANCE_KEYS
        for key in WITHHELD_CONFIG_KEYS:
            assert key not in data["config"], key
        for key in WITHHELD_INSTANCE_KEYS:
            assert key not in data["instance"], key
        assert "version" not in data["config"]["product"]
        body = str(data)
        for secret in ("0.1.0-rc.99", "hangar.corp.example", "Corp Hangar", instance.instance_id, "phc_secret"):
            assert secret not in body
        assert str(default_workspace.id) not in body

    def test_sign_in_pages_still_get_what_they_render(self, instance):
        data = APIClient().get(INSTANCE_URL).json()

        assert data["instance"]["is_setup_done"] is True
        assert "workspaces_exist" in data["instance"]
        for key in ("enable_signup", "is_email_password_enabled", "is_smtp_configured", "branding_name"):
            assert key in data["config"], key
        assert data["config"]["product"]["name"] == "Hangar"
        assert data["config"]["product"]["source_url"]

    def test_a_web_session_is_anonymous_here(self, instance):
        client = APIClient()
        client.force_authenticate(user=_user("member"))
        data = client.get(INSTANCE_URL).json()

        assert "instance_id" not in data["instance"]
        assert "default_workspace_id" not in data["config"]

    def test_an_unconfigured_instance_reveals_only_its_setup_state(self, db):
        data = APIClient().get(INSTANCE_URL).json()

        assert data["is_setup_done"] is False
        assert "version" not in data["product"]

    def test_the_response_is_not_reused_by_the_browser(self, instance):
        response = APIClient().get(INSTANCE_URL)

        assert "no-cache" in response["Cache-Control"]


@pytest.mark.contract
@pytest.mark.django_db
class TestConsoleAndMemberPayload:
    def test_a_verified_console_session_gets_everything(self, instance):
        admin = _user("admin")
        InstanceAdmin.objects.create(instance=instance, user=admin, role=20)
        client = APIClient()
        authenticate_admin(client, admin)

        data = client.get(INSTANCE_URL).json()

        assert data["instance"]["instance_id"] == instance.instance_id
        assert "api_token_minimum_role" in data["config"]

    def test_an_unverified_console_session_gets_the_public_answer(self, instance):
        admin = _user("admin")
        InstanceAdmin.objects.create(instance=instance, user=admin, role=20)
        client = APIClient()
        authenticate_admin(client, admin, verified=False)

        data = client.get(INSTANCE_URL).json()

        assert "instance_id" not in data["instance"]
        assert "api_token_minimum_role" not in data["config"]

    def test_a_signed_in_user_reads_the_rest_from_the_member_endpoint(self, instance, default_workspace):
        client = APIClient()
        client.force_authenticate(user=_user("member"))
        with patch.dict("os.environ", {"APP_VERSION": "0.1.0-rc.99"}):
            data = client.get(MEMBER_URL).json()

        assert data["config"]["default_workspace_id"] == str(default_workspace.id)
        assert data["config"]["product"]["version"] == "0.1.0-rc.99"
        assert "api_token_minimum_role" in data["config"]
        assert data["instance"]["current_version"] == "0.1.0-rc.99"

    def test_the_member_endpoint_requires_a_session(self, instance):
        response = APIClient().get(MEMBER_URL)

        assert response.status_code in (401, 403)

    @override_settings(DEBUG=False)
    def test_both_readers_share_one_cached_payload(self, instance):
        """Configuration writes invalidate the /api/instances/ entry; the member view must read that entry."""
        client = APIClient()
        client.force_authenticate(user=_user("member"))

        client.get(MEMBER_URL)

        assert cache.get(generate_cache_key("/api/instances/", None)) is not None


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/auth/forgot-password/", "/auth/spaces/forgot-password/"])
@patch("plane.authentication.views.app.password_management.is_email_delivery_configured", return_value=True)
@patch("plane.authentication.views.space.password_management.is_email_delivery_configured", return_value=True)
@patch("plane.authentication.views.app.password_management.forgot_password.delay")
@patch("plane.authentication.views.space.password_management.forgot_password.delay")
def test_forgot_password_does_not_reveal_whether_an_account_exists(
    space_mail, app_mail, _space_smtp, _app_smtp, url, instance
):
    existing = _user("existing")
    client = APIClient()

    known = client.post(url, {"email": existing.email}, format="json")
    unknown = client.post(url, {"email": "nobody-here@corp.example"}, format="json")

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert app_mail.call_count + space_mail.call_count == 1
