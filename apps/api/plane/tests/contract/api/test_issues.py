# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueType, Project, ProjectMember, State
from plane.ext.services import ensure_project_system_types


@pytest.fixture
def project(db, workspace, create_user):
    """Create a test project with the requesting user as an active member."""
    project = Project.objects.create(
        name="Test Project",
        identifier="TP",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        role=20,  # Admin
        is_active=True,
    )
    return project


@pytest.fixture
def state(db, workspace, project):
    return State.objects.create(
        name="Todo",
        project=project,
        workspace=workspace,
        group="backlog",
        default=True,
    )


@pytest.fixture
def issue(db, workspace, project, state, create_user):
    return Issue.objects.create(
        name="Test Issue",
        workspace=workspace,
        project=project,
        state=state,
        created_by=create_user,
    )


@pytest.mark.contract
class TestIssueListOrderByInjection:
    """Regression tests for GHSA-p885-6jpg-cr2p on the work-item list
    endpoint: GET /api/v1/workspaces/{slug}/projects/{project_id}/issues/.

    The raw ``order_by`` query parameter fell through the endpoint's hardcoded
    branch logic to ``issue_queryset.order_by(order_by_param)``, letting an
    attacker order by sensitive related columns (blind oracle) or crash the
    endpoint with an unknown field (HTTP 500). The fix sanitizes the parameter
    against ISSUE_ORDER_BY_ALLOWLIST before the branch logic runs.
    """

    def get_url(self, workspace_slug, project_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

    @pytest.mark.django_db
    def test_invalid_order_by_does_not_500(self, api_key_client, workspace, project, issue):
        """Unknown field used to raise FieldError → HTTP 500; now sanitized to
        the safe default and returns 200 (DoS half of the advisory)."""
        url = self.get_url(workspace.slug, project.id)
        response = api_key_client.get(url, {"order_by": "not_a_field"})

        assert response.status_code == status.HTTP_200_OK, f"Got {response.status_code}: {response.data!r}"

    @pytest.mark.django_db
    def test_relational_order_by_injection_does_not_500(self, api_key_client, workspace, project, issue):
        """Ordering by a related-table column (``created_by__password``) used to
        reach ``.order_by()`` raw, forming a blind ordering oracle. It is now
        neutralized to the safe default. (Deterministic neutralization is
        asserted in tests/unit/utils/test_order_by_sanitize.py.)"""
        url = self.get_url(workspace.slug, project.id)
        response = api_key_client.get(url, {"order_by": "created_by__password"})

        assert response.status_code == status.HTTP_200_OK, f"Got {response.status_code}: {response.data!r}"

    @pytest.mark.django_db
    def test_legitimate_order_by_still_works(self, api_key_client, workspace, project, issue):
        """A valid, allowlisted ordering value continues to return 200 —
        the sanitizer must not break legitimate ordering."""
        url = self.get_url(workspace.slug, project.id)

        for value in ["-created_at", "priority", "state__group", "sequence_id"]:
            response = api_key_client.get(url, {"order_by": value})
            assert response.status_code == status.HTTP_200_OK, (
                f"order_by={value!r} got {response.status_code}: {response.data!r}"
            )


@pytest.mark.contract
class TestIssueTypeHierarchyAPI:
    def get_list_url(self, workspace_slug, project_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

    def get_detail_url(self, workspace_slug, project_id, issue_id):
        return f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/"

    @pytest.mark.django_db
    def test_create_epic_through_standard_work_item_api(self, api_key_client, workspace, project, state):
        _, epic_type = ensure_project_system_types(project)

        response = api_key_client.post(
            self.get_list_url(workspace.slug, project.id),
            {"name": "API Epic", "state_id": str(state.id), "type_id": str(epic_type.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert str(response.data["type_id"]) == str(epic_type.id)
        assert response.data["is_epic"] is True

    @pytest.mark.django_db
    def test_rejects_type_not_linked_to_project(self, api_key_client, workspace, project, state):
        rogue_type = IssueType.objects.create(workspace=workspace, name="Unlinked")

        response = api_key_client.post(
            self.get_list_url(workspace.slug, project.id),
            {"name": "Invalid", "state_id": str(state.id), "type_id": str(rogue_type.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type_id" in response.data

    @pytest.mark.django_db
    def test_rejects_parent_assignment_for_epic(self, api_key_client, workspace, project, state):
        _, epic_type = ensure_project_system_types(project)
        epic = Issue.objects.create(
            name="Epic",
            workspace=workspace,
            project=project,
            state=state,
            type=epic_type,
        )
        parent = Issue.objects.create(name="Parent", workspace=workspace, project=project, state=state)

        response = api_key_client.patch(
            self.get_detail_url(workspace.slug, project.id, epic.id),
            {"parent_id": str(parent.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "parent_id" in response.data
