# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Administrative access must survive pinning a domain to an identity provider.

The God Mode console is the recovery path this deployment relies on. It
authenticates against the password directly rather than through the provider
adapters, so an administrator cannot pin themselves out of it — and, since the
second factor shipped, the credential that recovers an instance is a password
plus a registered security key rather than a password alone.

An application account in an unpinned domain also keeps password sign-in, because
the policy governs only the domains it lists. That behaviour is asserted here so
it cannot change silently, but it is a property of the policy rather than a
recommendation: each such account is a password-authenticated way into a domain
that pinning was meant to close.
"""

import uuid

import pytest
from django.test import Client
from django.urls import reverse
from plane.authentication.adapter.base import Adapter
from plane.authentication.adapter.error import AuthenticationException
from plane.db.models import User
from plane.license.models import InstanceAdmin, InstanceConfiguration
from plane.tests.contract.app import test_google_auth as _google_auth

# Re-exported so pytest resolves it from this module's namespace without the
# test parameter shadowing an imported symbol.
setup_instance = _google_auth.setup_instance

PINNED = "corp.com=google"
PASSWORD = "correct-horse-battery-staple-42"


@pytest.fixture
def pinned_domain(db):
    InstanceConfiguration.objects.update_or_create(
        key="SSO_ENFORCED_DOMAINS",
        defaults={"value": PINNED, "category": "SSO", "is_encrypted": False},
    )


def _adapter(provider, email):
    """A minimal adapter standing in for whichever provider is signing in."""
    adapter = Adapter.__new__(Adapter)
    adapter.provider = provider
    adapter.logger = __import__("logging").getLogger("test")
    return adapter, email


@pytest.mark.contract
@pytest.mark.django_db
def test_password_is_refused_for_an_address_in_a_pinned_domain(pinned_domain):
    adapter, email = _adapter("email", "person@corp.com")

    with pytest.raises(AuthenticationException):
        adapter.enforce_sso_domain_policy(email)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_administrator_outside_the_pinned_domain_keeps_password_sign_in(pinned_domain):
    """The recommended break-glass account: a different domain entirely."""
    adapter, email = _adapter("email", "breakglass@ops.example")

    adapter.enforce_sso_domain_policy(email)


@pytest.mark.contract
@pytest.mark.django_db
def test_god_mode_console_is_not_governed_by_the_domain_policy(pinned_domain, setup_instance):
    """God Mode checks the password itself, so an admin cannot be locked out.

    The same fact means a pinned domain does not restrict the console: its
    password is the only thing standing in front of it.
    """
    admin = User.objects.create(email="admin@corp.com", username=uuid.uuid4().hex, is_password_autoset=False)
    admin.set_password(PASSWORD)
    admin.save()
    InstanceAdmin.objects.create(instance=setup_instance, user=admin, role=20)

    response = Client(HTTP_USER_AGENT="Mozilla/5.0 test").post(
        reverse("instance-admin-sign-in"),
        {"email": admin.email, "password": PASSWORD},
    )

    # A redirect carrying no error_code means the console accepted the sign-in,
    # even though corp.com is pinned to Google for every application route.
    assert response.status_code == 302
    assert "error_code" not in response.url


@pytest.mark.contract
def test_admin_sign_in_and_sign_up_have_distinct_route_names():
    """Guards against the two routes sharing a name again.

    They both answered to "instance-admin-sign-in", so reverse() resolved to
    whichever was registered last — sign-up. Nothing in production depended on
    it because the panel posts to literal paths, but every test and any future
    caller using reverse() silently got the wrong endpoint.
    """
    sign_in = reverse("instance-admin-sign-in")
    sign_up = reverse("instance-admin-sign-up")

    assert sign_in != sign_up
    assert sign_in.endswith("/admins/sign-in/")
    assert sign_up.endswith("/admins/sign-up/")
