# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""An account that signs in through a provider has no Hangar password to set.

`is_password_autoset` is true for such an account, and the change-password
endpoint read that as "no old password to confirm" and let the request through.
So an account the administrator pinned to SSO could give itself a Hangar
password, and from then on the provider's own controls -- its second factor, its
lockout, its deprovisioning -- were no longer the only way in.

The refusal is the same shape as the one on the address, in
`test_federated_account_email_change.py`, and for the same underlying reason: the
provider owns this account, so the parts of it the provider governs are not
editable here.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from plane.db.models import FederatedIdentity, Profile, User

ISSUER = "https://accounts.google.com"
CHANGE_URL = "/auth/change-password/"
STRONG = "Tr0ub4dor&3-quite-long"


def _account(email, federated):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    if federated:
        # What federated_auth.py writes when it creates the account, and the
        # whole reason this was reachable: it is what tells the endpoint there
        # is no old password to confirm.
        user.is_password_autoset = True
        user.save()
        FederatedIdentity.objects.create(
            user=user,
            provider="google",
            issuer=ISSUER,
            subject=uuid.uuid4().hex,
            subject_format="",
            email_at_link=email,
            last_email=email,
        )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_cannot_set_a_password():
    client, user = _account("person@corp.com", federated=True)

    response = client.post(CHANGE_URL, {"new_password": STRONG}, format="json")

    assert response.status_code == 403
    user.refresh_from_db()
    assert not user.check_password(STRONG), "the provider-owned account was given a Hangar password"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_refusal_says_where_to_go_instead():
    """A 403 with no explanation reads as a bug in the console."""
    client, _user = _account("person@corp.com", federated=True)

    response = client.post(CHANGE_URL, {"new_password": STRONG}, format="json")

    assert "identity provider" in str(response.data).lower()


@pytest.mark.contract
@pytest.mark.django_db
def test_a_federated_account_cannot_set_one_by_supplying_an_old_password():
    """The guard must not depend on which fields the request happens to carry."""
    client, user = _account("person@corp.com", federated=True)

    response = client.post(CHANGE_URL, {"old_password": "anything", "new_password": STRONG}, format="json")

    assert response.status_code == 403
    user.refresh_from_db()
    assert not user.check_password(STRONG)


@pytest.mark.contract
@pytest.mark.django_db
def test_an_ordinary_account_can_still_set_one():
    """The guard is about who owns the account, not about passwords in general."""
    client, user = _account("person@example.com", federated=False)
    user.set_password("OldPassw0rd!-long-enough")
    user.is_password_autoset = False
    user.save()

    response = client.post(
        CHANGE_URL,
        {"old_password": "OldPassw0rd!-long-enough", "new_password": STRONG},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(STRONG)
