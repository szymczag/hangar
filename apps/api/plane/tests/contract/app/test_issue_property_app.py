# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueType, Project, ProjectMember, State, User, WorkspaceMember
from plane.db.models.issue_type import ProjectIssueType

from plane.ext.models import IssueProperty, IssuePropertyOption, IssuePropertyValue


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Types Project", identifier="TYP", workspace=workspace, created_by=create_user
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def state(db, project, workspace):
    return State.objects.create(
        name="Todo", group="unstarted", color="#fff", project=project, workspace=workspace, default=True
    )


@pytest.fixture
def issue_type(db, workspace, project):
    issue_type = IssueType.objects.create(workspace=workspace, name="Bug", is_epic=False)
    ProjectIssueType.objects.create(project=project, issue_type=issue_type)
    return issue_type


@pytest.fixture
def issue(db, project, workspace, state, issue_type):
    return Issue.objects.create(
        name="Some bug", project=project, workspace=workspace, state=state, type=issue_type
    )


def base_url(workspace, project):
    return f"/api/workspaces/{workspace.slug}/projects/{project.id}"


def make_role_client(workspace, project, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(email=f"user-{uid}@hangar.test", username=f"user_{uid}")
    WorkspaceMember.objects.create(workspace=workspace, member=user, role=role, is_active=True)
    ProjectMember.objects.create(project=project, member=user, role=role, is_active=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.contract
class TestIssueTypeCRUD:
    @pytest.mark.django_db
    def test_admin_creates_type(self, session_client, workspace, project):
        response = session_client.post(
            f"{base_url(workspace, project)}/issue-types/", {"name": "HR Request"}, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_epic"] is False
        assert ProjectIssueType.objects.filter(
            project=project, issue_type_id=response.data["id"]
        ).exists()

    @pytest.mark.django_db
    def test_member_cannot_create_type(self, workspace, project):
        client, _ = make_role_client(workspace, project, role=15)
        response = client.post(f"{base_url(workspace, project)}/issue-types/", {"name": "Nope"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_is_epic_cannot_be_injected(self, session_client, workspace, project):
        response = session_client.post(
            f"{base_url(workspace, project)}/issue-types/",
            {"name": "Sneaky", "is_epic": True},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert IssueType.objects.get(pk=response.data["id"]).is_epic is False

    @pytest.mark.django_db
    def test_delete_in_use_type_rejected(self, session_client, workspace, project, issue_type, issue):
        response = session_client.delete(f"{base_url(workspace, project)}/issue-types/{issue_type.id}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert IssueType.objects.filter(pk=issue_type.id).exists()

    @pytest.mark.django_db
    def test_delete_unused_type(self, session_client, workspace, project, issue_type):
        response = session_client.delete(f"{base_url(workspace, project)}/issue-types/{issue_type.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.contract
class TestIssueProperties:
    def create_property(self, client, workspace, project, issue_type, **overrides):
        payload = {"display_name": "Severity", "property_type": "select"}
        payload.update(overrides)
        return client.post(
            f"{base_url(workspace, project)}/issue-types/{issue_type.id}/properties/", payload, format="json"
        )

    @pytest.mark.django_db
    def test_create_and_list(self, session_client, workspace, project, issue_type):
        response = self.create_property(session_client, workspace, project, issue_type)
        assert response.status_code == status.HTTP_201_CREATED
        listing = session_client.get(f"{base_url(workspace, project)}/issue-types/{issue_type.id}/properties/")
        assert len(listing.data) == 1

    @pytest.mark.django_db
    def test_soft_delete_allows_recreate(self, session_client, workspace, project, issue_type):
        first = self.create_property(session_client, workspace, project, issue_type)
        session_client.delete(f"{base_url(workspace, project)}/properties/{first.data['id']}/")
        second = self.create_property(session_client, workspace, project, issue_type)
        assert second.status_code == status.HTTP_201_CREATED

    @pytest.mark.django_db
    def test_property_type_immutable(self, session_client, workspace, project, issue_type):
        prop = self.create_property(session_client, workspace, project, issue_type).data
        response = session_client.patch(
            f"{base_url(workspace, project)}/properties/{prop['id']}/",
            {"property_type": "text"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_is_multi_only_for_multi_types(self, session_client, workspace, project, issue_type):
        response = self.create_property(
            session_client, workspace, project, issue_type, property_type="text", is_multi=True
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_options_only_on_select(self, session_client, workspace, project, issue_type):
        prop = self.create_property(
            session_client, workspace, project, issue_type, display_name="Effort", property_type="number"
        ).data
        response = session_client.post(
            f"{base_url(workspace, project)}/properties/{prop['id']}/options/", {"name": "High"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_cross_project_property_access_denied(self, session_client, workspace, project, issue_type):
        # A type linked to a different project in the same workspace
        other_project = Project.objects.create(
            name="Other", identifier="OTH", workspace=workspace, created_by=None
        )
        other_type = IssueType.objects.create(workspace=workspace, name="Other Type")
        ProjectIssueType.objects.create(project=other_project, issue_type=other_type)
        other_prop = IssueProperty.objects.create(
            workspace=workspace, issue_type=other_type, display_name="Hidden", property_type="text"
        )
        response = session_client.patch(
            f"{base_url(workspace, project)}/properties/{other_prop.id}/",
            {"display_name": "Pwned"},
            format="json",
        )
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


@pytest.mark.contract
class TestPropertyValues:
    @pytest.fixture
    def text_prop(self, db, workspace, issue_type):
        return IssueProperty.objects.create(
            workspace=workspace, issue_type=issue_type, display_name="Notes", property_type="text"
        )

    @pytest.fixture
    def number_prop(self, db, workspace, issue_type):
        return IssueProperty.objects.create(
            workspace=workspace, issue_type=issue_type, display_name="Effort", property_type="number"
        )

    @pytest.fixture
    def select_prop(self, db, workspace, issue_type):
        prop = IssueProperty.objects.create(
            workspace=workspace, issue_type=issue_type, display_name="Severity", property_type="select"
        )
        IssuePropertyOption.objects.create(workspace=workspace, property=prop, name="High")
        return prop

    @pytest.fixture
    def multi_prop(self, db, workspace, issue_type):
        return IssueProperty.objects.create(
            workspace=workspace,
            issue_type=issue_type,
            display_name="Tags",
            property_type="multi_select",
            is_multi=True,
        )

    def values_url(self, workspace, project, issue):
        return f"{base_url(workspace, project)}/issues/{issue.id}/property-values/"

    @pytest.mark.django_db
    def test_round_trip(self, session_client, workspace, project, issue, text_prop, number_prop):
        payload = {str(text_prop.id): ["hello"], str(number_prop.id): ["42.5"]}
        response = session_client.post(self.values_url(workspace, project, issue), payload, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        get_response = session_client.get(self.values_url(workspace, project, issue))
        assert get_response.data[str(text_prop.id)] == ["hello"]
        assert get_response.data[str(number_prop.id)] == ["42.5"]

    @pytest.mark.django_db
    def test_invalid_number_rejected(self, session_client, workspace, project, issue, number_prop):
        response = session_client.post(
            self.values_url(workspace, project, issue), {str(number_prop.id): ["not-a-number"]}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_oversized_number_rejected(self, session_client, workspace, project, issue, number_prop):
        response = session_client.post(
            self.values_url(workspace, project, issue),
            {str(number_prop.id): ["1234567890123456789012345.123456"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_select_value_must_be_own_option(self, session_client, workspace, project, issue, select_prop):
        foreign_prop = IssueProperty.objects.create(
            workspace=workspace, issue_type=select_prop.issue_type, display_name="Other", property_type="select"
        )
        foreign_option = IssuePropertyOption.objects.create(
            workspace=workspace, property=foreign_prop, name="Foreign"
        )
        response = session_client.post(
            self.values_url(workspace, project, issue),
            {str(select_prop.id): [str(foreign_option.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_member_value_must_be_project_member(self, session_client, workspace, project, issue, issue_type):
        member_prop = IssueProperty.objects.create(
            workspace=workspace, issue_type=issue_type, display_name="Reviewer", property_type="member"
        )
        outsider = User.objects.create(email=f"out-{uuid4().hex[:8]}@hangar.test", username=f"out_{uuid4().hex[:8]}")
        response = session_client.post(
            self.values_url(workspace, project, issue), {str(member_prop.id): [str(outsider.id)]}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_required_property_enforced(self, session_client, workspace, project, issue, issue_type):
        required = IssueProperty.objects.create(
            workspace=workspace,
            issue_type=issue_type,
            display_name="Mandatory",
            property_type="text",
            is_required=True,
        )
        response = session_client.post(
            self.values_url(workspace, project, issue), {str(required.id): []}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_omitted_required_property_rejected(
        self, session_client, workspace, project, issue, issue_type
    ):
        IssueProperty.objects.create(
            workspace=workspace,
            issue_type=issue_type,
            display_name="Mandatory",
            property_type="text",
            is_required=True,
        )
        response = session_client.post(
            self.values_url(workspace, project, issue),
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_property_from_different_issue_type_rejected(
        self, session_client, workspace, project, issue
    ):
        other_type = IssueType.objects.create(workspace=workspace, name="Task")
        ProjectIssueType.objects.create(project=project, issue_type=other_type)
        foreign_prop = IssueProperty.objects.create(
            workspace=workspace,
            issue_type=other_type,
            display_name="Foreign",
            property_type="text",
        )
        response = session_client.post(
            self.values_url(workspace, project, issue),
            {str(foreign_prop.id): ["must not attach"]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_deleted_property_values_are_not_returned(
        self, session_client, workspace, project, issue, text_prop
    ):
        IssuePropertyValue.objects.create(
            workspace=workspace,
            project=project,
            issue=issue,
            property=text_prop,
            value_text="stale",
        )
        text_prop.delete()
        response = session_client.get(self.values_url(workspace, project, issue))
        assert response.status_code == status.HTTP_200_OK
        assert str(text_prop.id) not in response.data

    @pytest.mark.django_db
    def test_multi_select_multiple_rows(self, session_client, workspace, project, issue, multi_prop):
        options = [
            IssuePropertyOption.objects.create(workspace=issue.workspace, property=multi_prop, name=f"tag-{i}")
            for i in range(2)
        ]
        payload = {str(multi_prop.id): [str(o.id) for o in options]}
        response = session_client.post(self.values_url(workspace, project, issue), payload, format="json")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert IssuePropertyValue.objects.filter(issue=issue, property=multi_prop).count() == 2

    @pytest.mark.django_db
    def test_single_select_rejects_multiple(self, session_client, workspace, project, issue, select_prop):
        extra = IssuePropertyOption.objects.create(workspace=issue.workspace, property=select_prop, name="Low")
        first = IssuePropertyOption.objects.get(property=select_prop, name="High")
        response = session_client.post(
            self.values_url(workspace, project, issue),
            {str(select_prop.id): [str(first.id), str(extra.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_unknown_property_rejected(self, session_client, workspace, project, issue):
        response = session_client.post(
            self.values_url(workspace, project, issue), {str(uuid4()): ["x"]}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_guest_cannot_write_values(self, workspace, project, issue, text_prop):
        client, _ = make_role_client(workspace, project, role=5)
        response = client.post(
            self.values_url(workspace, project, issue), {str(text_prop.id): ["hi"]}, format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
