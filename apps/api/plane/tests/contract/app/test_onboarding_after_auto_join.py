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
from plane.license.models import InstanceConfiguration


def _person(email="person@corp.com"):
    user = User.objects.create(email=email, username=uuid.uuid4().hex)
    Profile.objects.get_or_create(user=user)
    return user


def _workspace(owner, slug="acme"):
    workspace = Workspace.objects.create(name="Acme", owner=owner, slug=slug)
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
    """Where no provider supplies the name, the step still has a job.

    Someone admitted by invitation may genuinely have no name recorded, and
    settling this for them would skip the only screen that asks for one.
    """
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


def _sync_enabled(value="1"):
    InstanceConfiguration.objects.update_or_create(
        key="ENABLE_GOOGLE_SYNC",
        defaults={"value": value, "category": "GOOGLE", "is_encrypted": False},
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_nothing_is_asked_of_someone_whose_provider_answers_all_of_it(db):
    """The screen would collect a name, display name and picture it cannot edit.

    Where attribute sync is on, all three are written by the provider on every
    sign-in: the fields render read-only and the avatar upload is not offered at
    all. Leaving the step open sent the person to a form with nothing on it they
    could change.
    """
    _sync_enabled()
    user = _person()
    user.last_login_medium = "google"
    user.save()
    owner = _person("owner@corp.com")
    WorkspaceMember.objects.create(workspace=_workspace(owner), member=user, role=15, is_active=True)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    profile = Profile.objects.get(user=user)
    assert profile.onboarding_step["profile_complete"] is True
    assert profile.onboarding_step["workspace_invite"] is True


@pytest.mark.contract
@pytest.mark.django_db
def test_such_an_account_never_reaches_onboarding_at_all(db):
    """is_onboarded is what the application routes on.

    Settling the step flags alone left it false, so the person was still sent to
    onboarding, which rendered its first screen and navigated away once it had
    loaded enough to know there was nothing to ask.
    """
    _sync_enabled()
    user = _person()
    user.last_login_medium = "google"
    user.save()
    owner = _person("owner@corp.com")
    WorkspaceMember.objects.create(workspace=_workspace(owner), member=user, role=15, is_active=True)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    assert Profile.objects.get(user=user).is_onboarded is True


@pytest.mark.contract
@pytest.mark.django_db
def test_a_provider_without_sync_still_asks(db):
    """Federation is not the question; whether the provider writes the name is."""
    _sync_enabled("0")
    user = _person()
    user.last_login_medium = "google"
    user.save()
    owner = _person("owner@corp.com")
    WorkspaceMember.objects.create(workspace=_workspace(owner), member=user, role=15, is_active=True)

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    profile = Profile.objects.get(user=user)
    assert profile.onboarding_step["profile_complete"] is False
    assert profile.is_onboarded is False


@pytest.mark.contract
@pytest.mark.django_db
def test_belonging_nowhere_is_still_left_alone_even_with_sync(db):
    """There is a workspace question to answer, so the screens still apply."""
    _sync_enabled()
    user = _person()
    user.last_login_medium = "google"
    user.save()

    post_user_auth_workflow(user=user, is_signup=False, request=None)

    profile = Profile.objects.get(user=user)
    assert profile.is_onboarded is False
    assert profile.onboarding_step["workspace_create"] is False
