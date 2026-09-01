# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The maintenance notice is read by people who cannot sign in, by design.

That is the whole point of the feature -- an outage is exactly when someone
cannot get in -- and it is also what makes it a disclosure surface. The tests
that matter most here are the ones proving an anonymous caller is served only
what the operator deliberately published.
"""

import uuid
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from plane.db.models import User
from plane.ext.models import InstanceMaintenanceNotice
from plane.license.models import InstanceAdmin
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin

setup_instance = _google_auth.setup_instance

PUBLIC_URL = "/api/maintenance/"
ADMIN_URL = "/api/instances/maintenance/"


@pytest.fixture(autouse=True)
def _clear_cache():
    """The view caches the row for ten seconds; tests must not inherit it."""
    cache.clear()
    yield
    cache.clear()


def _user(email):
    return User.objects.create(email=email, username=uuid.uuid4().hex)


@pytest.fixture
def admin_client(db, setup_instance):
    admin = _user("admin@ops.example")
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    return client


def _notice(**kwargs):
    defaults = {
        "is_enabled": True,
        "message": "Maintenance 22:00-22:30 today.",
        "severity": InstanceMaintenanceNotice.Severity.WARNING,
        "show_on_sign_in": False,
    }
    return InstanceMaintenanceNotice.objects.create(**{**defaults, **kwargs})


@pytest.mark.contract
@pytest.mark.django_db
def test_an_anonymous_caller_is_not_told_about_an_unpublished_notice():
    """The disclosure regression. An active notice is not public by default."""
    _notice(show_on_sign_in=False)

    response = APIClient().get(PUBLIC_URL)

    assert response.status_code == 200
    assert response.json()["notice"] is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_published_notice_reaches_someone_who_cannot_sign_in():
    _notice(show_on_sign_in=True)

    body = APIClient().get(PUBLIC_URL).json()["notice"]

    assert body["message"] == "Maintenance 22:00-22:30 today."
    assert body["severity"] == "warning"
    assert body["fingerprint"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_signed_in_reader_sees_an_unpublished_notice():
    """`show_on_sign_in` gates people without an account, not people with one."""
    _notice(show_on_sign_in=False)

    client = APIClient()
    client.force_authenticate(user=_user("member@corp.example"))

    assert client.get(PUBLIC_URL).json()["notice"] is not None


@pytest.mark.contract
@pytest.mark.django_db
def test_the_notice_is_never_held_by_a_shared_cache():
    """Guards against `@cache_response` being reintroduced over the gate above.

    The body depends on whether the caller is authenticated, so a cached copy
    would eventually be served to the wrong audience.
    """
    _notice(show_on_sign_in=True)

    assert APIClient().get(PUBLIC_URL)["Cache-Control"] == "no-store"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_window_that_has_not_opened_yet_shows_nothing():
    now = timezone.now()
    _notice(show_on_sign_in=True, starts_at=now + timedelta(hours=2), ends_at=now + timedelta(hours=3))

    assert APIClient().get(PUBLIC_URL).json()["notice"] is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_window_that_has_closed_shows_nothing():
    now = timezone.now()
    _notice(show_on_sign_in=True, starts_at=now - timedelta(hours=3), ends_at=now - timedelta(hours=1))

    assert APIClient().get(PUBLIC_URL).json()["notice"] is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_disabled_notice_shows_nothing():
    _notice(is_enabled=False, show_on_sign_in=True)

    assert APIClient().get(PUBLIC_URL).json()["notice"] is None


@pytest.mark.contract
@pytest.mark.django_db
def test_only_an_administrator_may_set_the_notice(db, setup_instance):
    ordinary = APIClient()
    ordinary.force_authenticate(user=_user("nobody@corp.example"))

    assert ordinary.patch(ADMIN_URL, {"message": "hi"}, format="json").status_code in (401, 403)
    assert APIClient().patch(ADMIN_URL, {"message": "hi"}, format="json").status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_administrator_raises_a_notice(admin_client):
    response = admin_client.patch(
        ADMIN_URL,
        {"is_enabled": True, "message": "Upgrading the database.", "severity": "critical"},
        format="json",
    )

    assert response.status_code == 200, response.content
    assert response.json()["is_active"] is True
    assert InstanceMaintenanceNotice.objects.count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_setting_the_notice_twice_edits_the_same_row(admin_client):
    admin_client.patch(ADMIN_URL, {"is_enabled": True, "message": "First."}, format="json")
    admin_client.patch(ADMIN_URL, {"message": "Second."}, format="json")

    assert InstanceMaintenanceNotice.objects.count() == 1
    assert InstanceMaintenanceNotice.objects.get().message == "Second."


@pytest.mark.contract
@pytest.mark.django_db
def test_a_bidirectional_override_is_refused(admin_client):
    """U+202E in a strip above the whole app can invert what it appears to say."""
    response = admin_client.patch(ADMIN_URL, {"message": "Maintenance at 22:00‮"}, format="json")

    assert response.status_code == 400
    assert "control or formatting characters" in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_line_break_is_refused(admin_client):
    response = admin_client.patch(ADMIN_URL, {"message": "One line\nTwo lines"}, format="json")

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_an_overlong_message_is_refused(admin_client):
    response = admin_client.patch(ADMIN_URL, {"message": "x" * 501}, format="json")

    assert response.status_code == 400
    assert "500 characters" in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unknown_severity_is_refused(admin_client):
    response = admin_client.patch(ADMIN_URL, {"message": "hi", "severity": "urgent"}, format="json")

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_a_window_that_ends_before_it_starts_is_refused(admin_client):
    now = timezone.now()
    response = admin_client.patch(
        ADMIN_URL,
        {
            "message": "hi",
            "starts_at": (now + timedelta(hours=3)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "before it ends" in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_window_that_already_ended_is_refused(admin_client):
    response = admin_client.patch(
        ADMIN_URL,
        {
            "is_enabled": True,
            "message": "hi",
            "ends_at": (timezone.now() - timedelta(hours=1)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert "already ended" in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_naive_datetime_is_refused(admin_client):
    response = admin_client.patch(ADMIN_URL, {"message": "hi", "starts_at": "2027-01-01T22:00:00"}, format="json")

    assert response.status_code == 400
    assert "timezone offset" in response.json()["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_enabling_a_notice_with_no_message_is_refused(admin_client):
    response = admin_client.patch(ADMIN_URL, {"is_enabled": True, "message": "   "}, format="json")

    assert response.status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_the_fingerprint_follows_the_wording_not_the_toggle(admin_client):
    """Dismissal keys off this, so switching a notice off and on must not re-nag."""
    admin_client.patch(ADMIN_URL, {"is_enabled": True, "message": "Same words."}, format="json")
    first = admin_client.patch(ADMIN_URL, {"is_enabled": False}, format="json").json()["fingerprint"]
    again = admin_client.patch(ADMIN_URL, {"is_enabled": True}, format="json").json()["fingerprint"]

    assert first == again

    edited = admin_client.patch(ADMIN_URL, {"message": "Different words."}, format="json")
    assert edited.json()["fingerprint"] != first


@pytest.mark.contract
@pytest.mark.django_db
def test_a_notice_can_be_raised_on_a_config_as_code_deployment(admin_client, settings):
    """Pins a deliberate departure from the house rule.

    `PATCH /api/instances/configurations/` returns 409 whenever SKIP_ENV_VAR is
    false, because those values are never read back when the environment is
    authoritative. This notice lives in its own table, so that premise does not
    hold -- and refusing the write would leave exactly the deployments that
    cannot edit configuration unable to announce an outage.
    """
    settings.SKIP_ENV_VAR = False

    response = admin_client.patch(ADMIN_URL, {"is_enabled": True, "message": "Rolling restart."}, format="json")

    assert response.status_code == 200, response.content
