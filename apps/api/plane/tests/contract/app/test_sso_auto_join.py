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
from django.utils import timezone

from plane.authentication.utils.sso_auto_join import (
    auto_join_projects,
    auto_join_workspaces,
    parse_auto_join,
    parse_auto_join_projects,
)
from plane.db.models import Project, ProjectMember, ProjectUserProperty, User, Workspace, WorkspaceMember


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


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def _project_config(auto_join="", enforced=""):
    return (
        patch(
            "plane.authentication.utils.sso_auto_join._configured_auto_join_projects",
            return_value=parse_auto_join_projects(auto_join),
        ),
        patch(
            "plane.authentication.utils.sso_domain_policy.get_configuration_value",
            return_value=(enforced,),
        ),
    )


@pytest.fixture
def target_project(db, target_workspace):
    owner = target_workspace.owner
    project = Project.objects.create(
        name="Platform", identifier="PLAT", workspace=target_workspace, created_by=owner
    )
    ProjectMember.objects.create(
        workspace=target_workspace, project=project, member=owner, role=20, is_active=True
    )
    return project


def _make_workspace_member(workspace, user, role=15):
    return WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)


def test_project_entries_require_a_workspace_and_an_identifier():
    assert parse_auto_join_projects("corp.com=engineering/PLAT:member") == {
        "corp.com": [("engineering", "PLAT", 15)]
    }
    # Without the workspace/project separator there is nothing to resolve.
    assert parse_auto_join_projects("corp.com=PLAT:member") == {}
    assert parse_auto_join_projects("corp.com=engineering/:member") == {}


def test_project_role_defaults_to_guest_and_rejects_unknown_roles():
    assert parse_auto_join_projects("corp.com=engineering/PLAT") == {"corp.com": [("engineering", "PLAT", 5)]}
    assert parse_auto_join_projects("corp.com=engineering/PLAT:superuser") == {}


@pytest.mark.django_db
def test_user_joins_the_configured_project(target_workspace, target_project, corp_user):
    _make_workspace_member(target_workspace, corp_user)
    join_patch, policy_patch = _project_config("corp.com=engineering/PLAT:member", "corp.com=google")

    with join_patch, policy_patch:
        joined = auto_join_projects(corp_user, provider="google")

    assert joined == [("engineering", "PLAT", 15)]
    membership = ProjectMember.objects.get(project=target_project, member=corp_user)
    assert membership.role == 15
    # ProjectMember.save() creates this; bulk_create would have skipped it.
    assert ProjectUserProperty.objects.filter(project=target_project, user=corp_user).exists()


@pytest.mark.django_db
def test_no_project_join_without_the_workspace_seat(target_workspace, target_project, corp_user):
    """A ProjectMember without a WorkspaceMember is a state nothing expects.

    The setting must not manufacture the workspace seat on its own.
    """
    join_patch, policy_patch = _project_config("corp.com=engineering/PLAT:member", "corp.com=google")

    with join_patch, policy_patch:
        joined = auto_join_projects(corp_user, provider="google")

    assert joined == []
    assert not ProjectMember.objects.filter(project=target_project, member=corp_user).exists()


@pytest.mark.django_db
def test_no_project_join_when_the_domain_is_not_pinned(target_workspace, target_project, corp_user):
    """The same gate as the workspace form, applied through shared code."""
    _make_workspace_member(target_workspace, corp_user)
    join_patch, policy_patch = _project_config("corp.com=engineering/PLAT:member", enforced="")

    with join_patch, policy_patch:
        joined = auto_join_projects(corp_user, provider="magic-code")

    assert joined == []
    assert not ProjectMember.objects.filter(project=target_project, member=corp_user).exists()


@pytest.mark.django_db
def test_archived_projects_are_skipped(target_workspace, target_project, corp_user):
    _make_workspace_member(target_workspace, corp_user)
    target_project.archived_at = timezone.now()
    target_project.save()
    join_patch, policy_patch = _project_config("corp.com=engineering/PLAT:member", "corp.com=google")

    with join_patch, policy_patch:
        assert auto_join_projects(corp_user, provider="google") == []


@pytest.mark.django_db
def test_existing_project_membership_is_never_modified(target_workspace, target_project, corp_user):
    _make_workspace_member(target_workspace, corp_user)
    ProjectMember.objects.create(
        workspace=target_workspace, project=target_project, member=corp_user, role=5, is_active=False
    )
    join_patch, policy_patch = _project_config("corp.com=engineering/PLAT:admin", "corp.com=google")

    with join_patch, policy_patch:
        joined = auto_join_projects(corp_user, provider="google")

    membership = ProjectMember.objects.get(project=target_project, member=corp_user)
    assert joined == []
    assert membership.role == 5
    assert membership.is_active is False


@pytest.mark.django_db
def test_unknown_identifier_is_skipped_without_failing_sign_in(target_workspace, corp_user):
    _make_workspace_member(target_workspace, corp_user)
    join_patch, policy_patch = _project_config("corp.com=engineering/NOPE:member", "corp.com=google")

    with join_patch, policy_patch:
        assert auto_join_projects(corp_user, provider="google") == []


@pytest.mark.django_db
def test_repeated_sign_in_does_not_duplicate_project_membership(target_workspace, target_project, corp_user):
    _make_workspace_member(target_workspace, corp_user)
    join_patch, policy_patch = _project_config("corp.com=engineering/PLAT:member", "corp.com=google")

    with join_patch, policy_patch:
        auto_join_projects(corp_user, provider="google")
        auto_join_projects(corp_user, provider="google")

    assert ProjectMember.objects.filter(project=target_project, member=corp_user).count() == 1

