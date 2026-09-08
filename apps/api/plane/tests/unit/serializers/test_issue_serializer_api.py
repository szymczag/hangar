# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.api.serializers.issue import IssueSerializer
from plane.db.models import Label, Project, ProjectMember, User


@pytest.fixture
def project(workspace):
    return Project.objects.create(name="Reference validation", identifier="REF", workspace=workspace)


def serializer_for(project, payload):
    return IssueSerializer(
        data={"name": "Test issue", **payload},
        context={"project_id": project.id, "workspace_id": project.workspace_id},
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueSerializerReferenceValidation:
    def test_rejects_non_member_assignee_without_disclosing_the_identifier(self, project):
        outsider = User.objects.create(email="outsider@example.com", username="outsider")
        serializer = serializer_for(project, {"assignees": [outsider.id]})

        assert not serializer.is_valid()
        assert serializer.errors["assignees"][0] == "One or more assignees are not active members of this project."
        assert str(outsider.id) not in str(serializer.errors)

    def test_rejects_entire_mixed_assignee_list(self, project, create_user):
        ProjectMember.objects.create(project=project, member=create_user, role=15, is_active=True)
        outsider = User.objects.create(email="mixed-outsider@example.com", username="mixed-outsider")
        serializer = serializer_for(project, {"assignees": [create_user.id, outsider.id]})

        assert not serializer.is_valid()
        assert "assignees" in serializer.errors

    def test_rejects_foreign_label_without_disclosing_the_identifier(self, project, workspace):
        other_project = Project.objects.create(name="Other", identifier="OTHER", workspace=workspace)
        foreign_label = Label.objects.create(name="Foreign", project=other_project, workspace=workspace)
        serializer = serializer_for(project, {"labels": [foreign_label.id]})

        assert not serializer.is_valid()
        assert serializer.errors["labels"][0] == "One or more labels do not belong to this project."
        assert str(foreign_label.id) not in str(serializer.errors)

    def test_accepts_and_deduplicates_valid_references(self, project, workspace, create_user):
        ProjectMember.objects.create(project=project, member=create_user, role=15, is_active=True)
        label = Label.objects.create(name="Valid", project=project, workspace=workspace)
        serializer = serializer_for(
            project,
            {"assignees": [create_user.id, create_user.id], "labels": [label.id, label.id]},
        )

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["assignees"] == [create_user.id]
        assert serializer.validated_data["labels"] == [label.id]
