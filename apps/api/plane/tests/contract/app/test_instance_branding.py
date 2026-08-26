# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The sign-in logo is public by necessity and therefore held to the same rules.

It dresses a page seen before anyone has an account, so it must be readable
without a session — which puts it in the same category as user avatars, not
workspace logos. Being public is exactly why the raster validation that guards
the other inline images has to cover it too.
"""

import uuid

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from plane.db.models import FileAsset, User
from plane.license.models import InstanceAdmin, InstanceConfiguration
from plane.tests.contract.app import test_google_auth as _google_auth
from plane.tests.support.admin_session import authenticate_admin
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION

setup_instance = _google_auth.setup_instance

URL = "/api/instances/branding/logo/"


def _user(email):
    return User.objects.create(email=email, username=uuid.uuid4().hex)


def _seed(key, value=""):
    """The suite runs with --nomigrations, so seeded rows are arranged here."""
    InstanceConfiguration.objects.update_or_create(
        key=key, defaults={"value": value, "category": "BRANDING", "is_encrypted": False}
    )


def _asset(entity_type, **kwargs):
    return FileAsset.objects.create(
        attributes={"type": "image/png"},
        asset="instance/logo.png",
        entity_type=entity_type,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
        **kwargs,
    )


@pytest.fixture
def admin_client(db, setup_instance):
    admin = _user("admin@ops.example")
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)
    client = APIClient()
    authenticate_admin(client, admin)
    return client


@pytest.mark.contract
@pytest.mark.django_db
def test_only_an_administrator_may_change_the_logo(db, setup_instance):
    ordinary = APIClient()
    ordinary.force_authenticate(user=_user("nobody@corp.com"))

    assert ordinary.delete(URL).status_code in (401, 403)
    assert APIClient().delete(URL).status_code in (401, 403)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_logo_is_readable_without_signing_in(db):
    """The page it appears on is seen before anyone has a session."""
    asset = _asset(FileAsset.EntityTypeContext.INSTANCE_LOGO)

    response = APIClient().get(f"/api/assets/v2/static/{asset.id}/")

    assert response.status_code in (200, 302)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unvalidated_logo_is_not_served(db):
    """Public and inline, so the raster marker is what makes it eligible."""
    asset = _asset(FileAsset.EntityTypeContext.INSTANCE_LOGO)
    FileAsset.objects.filter(pk=asset.pk).update(upload_validation_version=0)

    assert APIClient().get(f"/api/assets/v2/static/{asset.id}/").status_code == 404


@pytest.mark.contract
@pytest.mark.django_db
def test_a_non_image_logo_is_not_served(db):
    asset = _asset(FileAsset.EntityTypeContext.INSTANCE_LOGO)
    FileAsset.objects.filter(pk=asset.pk).update(attributes={"type": "text/html"})

    assert APIClient().get(f"/api/assets/v2/static/{asset.id}/").status_code == 404


@pytest.mark.contract
@pytest.mark.django_db
def test_clearing_the_logo_returns_to_the_wordmark(admin_client):
    InstanceConfiguration.objects.update_or_create(
        key="INSTANCE_LOGO_ASSET_ID",
        defaults={"value": str(uuid.uuid4()), "category": "BRANDING", "is_encrypted": False},
    )

    assert admin_client.delete(URL).status_code == 204
    assert InstanceConfiguration.objects.get(key="INSTANCE_LOGO_ASSET_ID").value == ""


@pytest.mark.contract
@pytest.mark.django_db
def test_a_request_without_a_file_is_refused(admin_client):
    assert admin_client.post(URL, {}, format="multipart").status_code == 400


@pytest.mark.contract
@pytest.mark.django_db
def test_branding_is_reported_to_anyone_opening_the_sign_in_page(db, setup_instance):
    """The page renders before authentication, so the values must too."""
    for key, value in (
        ("INSTANCE_BRANDING_NAME", "Example Org"),
        ("INSTANCE_SIGN_IN_HEADER", "Work securely."),
        ("INSTANCE_SIGN_IN_SUBHEADER", "Sign in to continue."),
    ):
        InstanceConfiguration.objects.update_or_create(
            key=key, defaults={"value": value, "category": "BRANDING", "is_encrypted": False}
        )

    cache.clear()
    response = APIClient().get("/api/instances/")

    assert response.status_code == 200
    config = response.data["config"]
    assert config["branding_name"] == "Example Org"
    assert config["sign_in_header"] == "Work securely."
    assert config["sign_in_subheader"] == "Sign in to continue."


@pytest.mark.contract
@pytest.mark.django_db
def test_an_instance_that_set_nothing_reports_empty_branding(db, setup_instance):
    """Empty means the built-in wording, so nothing changes for anyone else."""
    cache.clear()
    response = APIClient().get("/api/instances/")

    config = response.data["config"]
    assert config["branding_name"] == ""
    assert config["logo_url"] == ""


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    ["red", "#fff", "#12345g", "#123456; background-image: url(https://evil.test/x)", "javascript:alert(1)"],
)
def test_a_colour_that_is_not_a_hex_colour_is_refused(admin_client, value):
    """These reach a style attribute on the page that collects passwords."""
    response = admin_client.patch("/api/instances/configurations/", {"INSTANCE_ACCENT_COLOR": value}, format="json")

    assert response.status_code == 400
    assert "INSTANCE_ACCENT_COLOR" in response.data["error"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_hex_colour_is_accepted_and_reported(admin_client, db, setup_instance):
    _seed("INSTANCE_ACCENT_COLOR")
    _seed("INSTANCE_LOGIN_BACKDROP_COLOR")

    saved = admin_client.patch(
        "/api/instances/configurations/",
        {"INSTANCE_ACCENT_COLOR": "#1D4ED8", "INSTANCE_LOGIN_BACKDROP_COLOR": "#0b1220"},
        format="json",
    )
    assert saved.status_code == 200, saved.data

    cache.clear()
    config = APIClient().get("/api/instances/").data["config"]
    assert config["accent_color"] == "#1D4ED8"
    assert config["login_backdrop_color"] == "#0b1220"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_colour_written_around_the_api_is_still_not_served(db, setup_instance):
    """Read-side check, for a value that never passed the write-side one."""
    InstanceConfiguration.objects.update_or_create(
        key="INSTANCE_ACCENT_COLOR",
        defaults={
            "value": "#000; background: url(https://evil.test/x)",
            "category": "BRANDING",
            "is_encrypted": False,
        },
    )

    cache.clear()
    assert APIClient().get("/api/instances/").data["config"]["accent_color"] == ""


@pytest.mark.contract
@pytest.mark.django_db
def test_the_licence_notice_is_shown_unless_it_is_turned_off(admin_client, db, setup_instance):
    """On by default: an upgrade must not quietly stop making the source offer."""
    _seed("INSTANCE_SHOW_LICENSE_NOTICE", "1")

    cache.clear()
    assert APIClient().get("/api/instances/").data["config"]["show_license_notice"] is True

    admin_client.patch("/api/instances/configurations/", {"INSTANCE_SHOW_LICENSE_NOTICE": "0"}, format="json")

    cache.clear()
    assert APIClient().get("/api/instances/").data["config"]["show_license_notice"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_background_is_readable_without_signing_in(db):
    asset = _asset(FileAsset.EntityTypeContext.INSTANCE_LOGIN_BACKGROUND)

    assert APIClient().get(f"/api/assets/v2/static/{asset.id}/").status_code in (200, 302)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unknown_branding_image_is_refused(admin_client):
    assert admin_client.delete("/api/instances/branding/images/favicon/").status_code == 404
