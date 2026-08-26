# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Someone auto-joined into a workspace must not be sent to create one.

Onboarding routes on the profile's own flags rather than on membership, and
auto-join adds a WorkspaceMember directly without creating an invitation. So a
person it admitted reached the "create a workspace" step with no invitation to
accept — and where workspace creation is restricted, no way out of that screen.
"""

import uuid

import pytest

from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.db.models import Profile, User, Workspace, WorkspaceMember


def _person(email="person@corp.com"):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    return user


def _workspace(owner, slug="securitum"):
    workspace = Workspace.objects.create(name="Securitum", owner=owner, slug=slug)
    return workspace


@pytest.mark.contract
@pytest.mark.django_db
def test_a_membership_settles_the_workspace_steps(db):
    user = _person()
    owner = _person("owner@corp.com")
    workspace = _workspace(owner)
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    profile = Profile.objects.get(user=user)
    assert profile.onboarding_step["workspace_create"] is True
    assert profile.onboarding_step["workspace_join"] is True
    assert profile.last_workspace_id == workspace.id


@pytest.mark.contract
@pytest.mark.django_db
def test_the_profile_step_is_left_for_the_person_to_complete(db):
    """It collects a display name, which nobody else can supply."""
    user = _person()
    owner = _person("owner@corp.com")
    WorkspaceMember.objects.create(workspace=_workspace(owner), member=user, role=15, is_active=True)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    assert Profile.objects.get(user=user).onboarding_step["profile_complete"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_someone_who_belongs_nowhere_is_left_alone(db):
    """The screen is right for them: they do have to create or be invited."""
    user = _person()

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    profile = Profile.objects.get(user=user)
    assert profile.onboarding_step["workspace_create"] is False
    assert profile.last_workspace_id is None


@pytest.mark.contract
@pytest.mark.django_db
def test_a_deactivated_membership_does_not_count(db):
    user = _person()
    owner = _person("owner@corp.com")
    WorkspaceMember.objects.create(workspace=_workspace(owner), member=user, role=15, is_active=False)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    assert Profile.objects.get(user=user).onboarding_step["workspace_create"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_an_existing_last_workspace_is_not_moved(db):
    """Signing in must not relocate someone who already chose where they work."""
    user = _person()
    owner = _person("owner@corp.com")
    first = _workspace(owner, slug="first")
    second = _workspace(owner, slug="second")
    WorkspaceMember.objects.create(workspace=first, member=user, role=15, is_active=True)
    WorkspaceMember.objects.create(workspace=second, member=user, role=15, is_active=True)
    Profile.objects.filter(user=user).update(last_workspace_id=second.id)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    assert Profile.objects.get(user=user).last_workspace_id == second.id
