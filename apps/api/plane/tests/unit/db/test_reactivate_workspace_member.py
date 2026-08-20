# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from plane.tests.factories import (
    ProjectFactory,
    ProjectMemberFactory,
    UserFactory,
    WorkspaceFactory,
    WorkspaceMemberFactory,
)


@pytest.mark.django_db
def test_reactivates_workspace_membership_without_reactivating_related_records():
    user = UserFactory(email="member@hangar.test", is_active=False)
    workspace = WorkspaceFactory(slug="engineering")
    workspace_member = WorkspaceMemberFactory(workspace=workspace, member=user, is_active=False)
    project = ProjectFactory(workspace=workspace)
    project_member = ProjectMemberFactory(project=project, member=user, is_active=False)
    stdout = StringIO()

    call_command(
        "reactivate_workspace_member",
        " engineering ",
        " MEMBER@HANGAR.TEST ",
        stdout=stdout,
    )

    workspace_member.refresh_from_db()
    project_member.refresh_from_db()
    user.refresh_from_db()
    assert workspace_member.is_active is True
    assert project_member.is_active is False
    assert user.is_active is False
    output = stdout.getvalue()
    assert "reactivated successfully" in output
    assert "1 project membership(s) remain inactive" in output
    assert "account for member@hangar.test is deactivated" in output


@pytest.mark.django_db
def test_already_active_workspace_membership_is_idempotent():
    user = UserFactory(email="active@hangar.test")
    workspace = WorkspaceFactory(slug="active-workspace")
    WorkspaceMemberFactory(workspace=workspace, member=user, is_active=True)
    stdout = StringIO()

    call_command("reactivate_workspace_member", workspace.slug, user.email, stdout=stdout)

    assert "already an active member" in stdout.getvalue()


@pytest.mark.django_db
def test_rejects_user_without_workspace_membership():
    user = UserFactory(email="outsider@hangar.test")
    workspace = WorkspaceFactory(slug="private-workspace")

    with pytest.raises(CommandError, match="is not a member of workspace"):
        call_command("reactivate_workspace_member", workspace.slug, user.email)


@pytest.mark.django_db
def test_rejects_unknown_user_and_workspace():
    with pytest.raises(CommandError, match="User with missing@hangar.test does not exist"):
        call_command("reactivate_workspace_member", "missing", "missing@hangar.test")

    user = UserFactory(email="known@hangar.test")
    with pytest.raises(CommandError, match="Workspace with slug missing does not exist"):
        call_command("reactivate_workspace_member", "missing", user.email)
