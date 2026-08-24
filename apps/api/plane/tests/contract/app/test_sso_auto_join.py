# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Auto-join places a federated user into a workspace on sign-in.

The security-relevant part is what it refuses to do. Membership is granted on
the strength of an email domain, so the domain must be pinned to a provider
first; otherwise any other enabled sign-in method would become a way onto the
workspace.
"""

import uuid
from unittest.mock import patch

import pytest

from plane.authentication.utils.sso_auto_join import auto_join_workspaces, parse_auto_join
from plane.db.models import User, Workspace, WorkspaceMember


def _config(auto_join="", enforced=""):
    """Patch both settings the auto-join decision reads."""
    return (
        patch(
            "plane.authentication.utils.sso_auto_join._configured_auto_join",
            return_value=parse_auto_join(auto_join),
        ),
        patch(
            "plane.authentication.utils.sso_domain_policy.get_configuration_value",
            return_value=(enforced,),
        ),
    )


@pytest.fixture
def target_workspace(db):
    owner = User.objects.create(email=f"owner-{uuid.uuid4().hex[:8]}@example.com", username=uuid.uuid4().hex)
    workspace = Workspace.objects.create(name="Engineering", owner=owner, slug="engineering")
    WorkspaceMember.objects.create(workspace=workspace, member=owner, role=20, is_active=True)
    return workspace


@pytest.fixture
def corp_user(db):
    return User.objects.create(email="person@corp.com", username=uuid.uuid4().hex)


def test_parse_defaults_to_the_least_privileged_role():
    assert parse_auto_join("corp.com=engineering") == {"corp.com": [("engineering", 5)]}
    assert parse_auto_join("corp.com=engineering:member") == {"corp.com": [("engineering", 15)]}
    assert parse_auto_join("corp.com=engineering:admin") == {"corp.com": [("engineering", 20)]}


def test_parse_rejects_unknown_roles_rather_than_guessing():
    assert parse_auto_join("corp.com=engineering:superuser") == {}


def test_parse_skips_malformed_entries_without_losing_the_rest():
    assert parse_auto_join("nonsense,=engineering,corp.com=,corp.com=engineering:member") == {
        "corp.com": [("engineering", 15)]
    }


@pytest.mark.django_db
def test_user_joins_the_configured_workspace(target_workspace, corp_user):
    auto_join_patch, policy_patch = _config("corp.com=engineering:member", "corp.com=google")
    with auto_join_patch, policy_patch:
        joined = auto_join_workspaces(corp_user, provider="google")

    assert joined == [("engineering", 15)]
    membership = WorkspaceMember.objects.get(workspace=target_workspace, member=corp_user)
    assert membership.role == 15
    assert membership.is_active is True


@pytest.mark.django_db
def test_no_join_when_the_domain_is_not_pinned_to_a_provider(target_workspace, corp_user):
    """The gate that makes auto-join safe.

    Without domain pinning, a magic-code or password sign-in at the same
    domain would be handed a seat in the workspace.
    """
    auto_join_patch, policy_patch = _config("corp.com=engineering:member", enforced="")
    with auto_join_patch, policy_patch:
        joined = auto_join_workspaces(corp_user, provider="magic-code")

    assert joined == []
    assert not WorkspaceMember.objects.filter(workspace=target_workspace, member=corp_user).exists()


@pytest.mark.django_db
def test_no_join_when_the_provider_is_not_the_pinned_one(target_workspace, corp_user):
    auto_join_patch, policy_patch = _config("corp.com=engineering:member", "corp.com=google")
    with auto_join_patch, policy_patch:
        joined = auto_join_workspaces(corp_user, provider="magic-code")

    assert joined == []
    assert not WorkspaceMember.objects.filter(workspace=target_workspace, member=corp_user).exists()


@pytest.mark.django_db
def test_other_domains_are_untouched(target_workspace, db):
    outsider = User.objects.create(email="person@other.com", username=uuid.uuid4().hex)
    auto_join_patch, policy_patch = _config("corp.com=engineering:member", "corp.com=google")
    with auto_join_patch, policy_patch:
        joined = auto_join_workspaces(outsider, provider="google")

    assert joined == []
    assert not WorkspaceMember.objects.filter(workspace=target_workspace, member=outsider).exists()


@pytest.mark.django_db
def test_existing_membership_is_never_modified(target_workspace, corp_user):
    """An admin who lowered someone's role must not have it restored on login."""
    WorkspaceMember.objects.create(workspace=target_workspace, member=corp_user, role=5, is_active=False)

    auto_join_patch, policy_patch = _config("corp.com=engineering:admin", "corp.com=google")
    with auto_join_patch, policy_patch:
        joined = auto_join_workspaces(corp_user, provider="google")

    membership = WorkspaceMember.objects.get(workspace=target_workspace, member=corp_user)
    assert joined == []
    assert membership.role == 5
    assert membership.is_active is False


@pytest.mark.django_db
def test_missing_workspace_is_skipped_without_failing_sign_in(corp_user):
    auto_join_patch, policy_patch = _config("corp.com=does-not-exist:member", "corp.com=google")
    with auto_join_patch, policy_patch:
        assert auto_join_workspaces(corp_user, provider="google") == []


@pytest.mark.django_db
def test_repeated_sign_in_does_not_duplicate_membership(target_workspace, corp_user):
    auto_join_patch, policy_patch = _config("corp.com=engineering:member", "corp.com=google")
    with auto_join_patch, policy_patch:
        auto_join_workspaces(corp_user, provider="google")
        auto_join_workspaces(corp_user, provider="google")

    assert WorkspaceMember.objects.filter(workspace=target_workspace, member=corp_user).count() == 1
