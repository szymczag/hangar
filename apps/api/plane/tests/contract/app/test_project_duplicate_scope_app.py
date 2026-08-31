# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Authorization contract for ``ProjectDuplicateEndpoint``.

Duplicating a project reads that project's entire object graph, so the endpoint
is a read of everything the source contains as much as it is a write. Two
independent authorizations therefore have to hold, and these tests pin both:

* **Reading the source.** ``allow_permission(..., level="PROJECT")`` requires an
  active ``ProjectMember`` row on the project named in the URL. Without it, a
  workspace member who is not in the project could copy a ``network=SECRET``
  project's structure into one they own -- the same class of cross-project read
  that ``test_deploy_board_project_scope_app.py`` covers for deploy boards.
  This is also why the source id is a URL kwarg: ``allow_permission`` resolves
  its subject from ``kwargs["project_id"]`` and cannot see a body-supplied id.
* **Creating the copy.** ``ProjectViewSet.create`` requires workspace
  ADMIN/MEMBER. A project ADMIN who is only a workspace GUEST must not be able
  to mint a project by going through duplicate.
"""

from uuid import uuid4

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Project, ProjectMember, User, Workspace, WorkspaceMember

ADMIN = 20
MEMBER = 15
GUEST = 5

SECRET = 0
PUBLIC = 2


def duplicate_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/duplicate/"


def make_user(prefix):
    unique_id = uuid4().hex[:8]
    user = User.objects.create(email=f"{prefix}-{unique_id}@example.test", username=f"{prefix}_{unique_id}")
    user.set_password("test-password")
    user.save()
    return user


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def secret_project(db, workspace, create_user):
    """A secret project that ``create_user`` owns and is a member of."""
    project = Project.objects.create(
        name="Secret Project",
        identifier="SECRET",
        network=SECRET,
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=ADMIN)
    return project


@pytest.fixture
def public_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Public Project",
        identifier="PUB",
        network=PUBLIC,
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=ADMIN)
    return project


@pytest.fixture
def outsider(db, workspace):
    """A workspace MEMBER who belongs to an unrelated project, not the source.

    Membership of *some* project matters: it means a refusal here is the
    cross-project scoping working, not merely the absence of any project role.
    """
    user = make_user("outsider")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=MEMBER)
    other = Project.objects.create(name="Outsider Project", identifier="OUT", workspace=workspace, created_by=user)
    ProjectMember.objects.create(project=other, member=user, workspace=workspace, role=ADMIN)
    return user


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectDuplicateScope:
    @pytest.fixture(autouse=True)
    def clear_throttles(self):
        """The duplicate endpoint is throttled per user and per workspace, and
        every test here shares one workspace slug. Without this the suite
        throttles itself."""
        cache.clear()

    def test_non_member_cannot_duplicate_a_secret_project(self, outsider, workspace, secret_project):
        """The headline case: no copy, and nothing created."""
        before = Project.objects.count()

        response = client_for(outsider).post(duplicate_url(workspace.slug, secret_project.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before

    def test_non_member_cannot_duplicate_a_public_project(self, outsider, workspace, public_project):
        """Unlike ``ProjectViewSet.retrieve``, duplicate does not soften to 409.

        Reading a public project's metadata is not the same as copying every
        state, label and estimate inside it.
        """
        before = Project.objects.count()

        response = client_for(outsider).post(duplicate_url(workspace.slug, public_project.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before

    def test_project_member_cannot_duplicate(self, workspace, public_project):
        """ADMIN of the source is required, not MEMBER.

        The copy re-links the source's custom work item types, and
        `IssueTypeDetailEndpoint` authorizes a mutation by ADMIN of *any* project
        linking the type. Since the caller becomes ADMIN of the copy, letting a
        MEMBER duplicate would hand them admin control over type and property
        definitions shared with projects they do not administer.
        """
        member = make_user("member")
        WorkspaceMember.objects.create(workspace=workspace, member=member, role=MEMBER)
        ProjectMember.objects.create(project=public_project, member=member, workspace=workspace, role=MEMBER)
        before = Project.objects.count()

        response = client_for(member).post(duplicate_url(workspace.slug, public_project.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before

    def test_project_guest_cannot_duplicate(self, workspace, public_project):
        guest = make_user("guest")
        WorkspaceMember.objects.create(workspace=workspace, member=guest, role=MEMBER)
        ProjectMember.objects.create(project=public_project, member=guest, workspace=workspace, role=GUEST)
        before = Project.objects.count()

        response = client_for(guest).post(duplicate_url(workspace.slug, public_project.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before

    def test_workspace_guest_who_is_project_admin_cannot_duplicate(self, workspace, public_project):
        """Project role does not confer the right to create a new project."""
        user = make_user("wsguest")
        WorkspaceMember.objects.create(workspace=workspace, member=user, role=GUEST)
        ProjectMember.objects.create(project=public_project, member=user, workspace=workspace, role=ADMIN)
        before = Project.objects.count()

        response = client_for(user).post(duplicate_url(workspace.slug, public_project.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before

    def test_workspace_admin_who_is_not_a_project_member_cannot_duplicate(self, workspace, secret_project):
        """``allow_permission``'s escalation branch still requires a membership row."""
        admin = make_user("wsadmin")
        WorkspaceMember.objects.create(workspace=workspace, member=admin, role=ADMIN)
        before = Project.objects.count()

        response = client_for(admin).post(duplicate_url(workspace.slug, secret_project.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before

    def test_workspace_admin_who_is_a_project_member_can_duplicate(self, workspace, secret_project):
        admin = make_user("wsadmin2")
        WorkspaceMember.objects.create(workspace=workspace, member=admin, role=ADMIN)
        ProjectMember.objects.create(project=secret_project, member=admin, workspace=workspace, role=GUEST)

        response = client_for(admin).post(duplicate_url(workspace.slug, secret_project.id), {}, format="json")

        assert response.status_code == status.HTTP_201_CREATED

    def test_project_in_another_workspace_is_refused(self, db, create_user, workspace, session_client):
        """A project id from a workspace the caller cannot name must not resolve."""
        other_owner = make_user("otherowner")
        other_workspace = Workspace.objects.create(
            name="Other Workspace", owner=other_owner, slug=f"other-{uuid4().hex[:8]}"
        )
        WorkspaceMember.objects.create(workspace=other_workspace, member=other_owner, role=ADMIN)
        foreign = Project.objects.create(
            name="Foreign", identifier="FGN", workspace=other_workspace, created_by=other_owner
        )
        ProjectMember.objects.create(project=foreign, member=other_owner, workspace=other_workspace, role=ADMIN)
        before = Project.objects.count()

        # The caller is an admin of `workspace`, and names their own slug with
        # someone else's project id.
        response = session_client.post(duplicate_url(workspace.slug, foreign.id), {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Project.objects.count() == before
