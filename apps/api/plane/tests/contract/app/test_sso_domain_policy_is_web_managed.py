# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The domain policy must be manageable from the admin panel.

An operator editing these in the UI expects the change to take effect. That
only holds because SKIP_ENV_VAR defaults to on, which makes the stored
configuration authoritative and the environment variable merely the seed
value. If that default were ever flipped, the panel would silently become
read-only for these settings, so the precedence is pinned here.
"""

import os
from unittest.mock import patch

import pytest

from plane.authentication.utils.sso_auto_join import _configured_auto_join
from plane.authentication.utils.sso_domain_policy import allowed_providers_for_email
from plane.license.models import InstanceConfiguration


@pytest.fixture
def stored_policy(db):
    InstanceConfiguration.objects.update_or_create(
        key="SSO_ENFORCED_DOMAINS",
        defaults={"value": "corp.com=google", "category": "SSO", "is_encrypted": False},
    )
    InstanceConfiguration.objects.update_or_create(
        key="SSO_AUTO_JOIN_WORKSPACES",
        defaults={"value": "corp.com=engineering:member", "category": "SSO", "is_encrypted": False},
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_stored_domain_policy_is_read_back(stored_policy):
    assert allowed_providers_for_email("person@corp.com") == {"google"}


@pytest.mark.contract
@pytest.mark.django_db
def test_stored_auto_join_is_read_back(stored_policy):
    assert _configured_auto_join() == {"corp.com": [("engineering", 15)]}


@pytest.mark.contract
@pytest.mark.django_db
def test_panel_value_wins_over_the_environment_variable(stored_policy):
    """Editing in the panel must not be silently overridden by a stale env var."""
    with patch.dict(os.environ, {"SSO_ENFORCED_DOMAINS": "corp.com=saml"}):
        assert allowed_providers_for_email("person@corp.com") == {"google"}


@pytest.mark.contract
@pytest.mark.django_db
def test_environment_seeds_the_value_only_when_nothing_is_stored(db):
    InstanceConfiguration.objects.filter(key="SSO_ENFORCED_DOMAINS").delete()

    with patch.dict(os.environ, {"SSO_ENFORCED_DOMAINS": "corp.com=saml"}):
        assert allowed_providers_for_email("person@corp.com") == {"saml"}
