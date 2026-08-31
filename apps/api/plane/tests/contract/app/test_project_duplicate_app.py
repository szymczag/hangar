# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Behaviour contract for ``ProjectDuplicateEndpoint``.

Authorization lives in ``test_project_duplicate_scope_app.py``; this file pins
what a copy actually contains. Several assertions here guard silent failures
rather than loud ones -- a dropped triage state, a row whose ``workspace_id``
was never set because ``bulk_create`` skipped ``save()``, or a foreign key on
the copy still pointing into the source.
"""

import pytest
from rest_framework import status

from plane.db.models import (
    Cycle,
    Estimate,
    EstimatePoint,
    Intake,
    IssueType,
    IssueView,
    Label,
    Module,
    Project,
    ProjectIdentifier,
    ProjectMember,
    ProjectUserProperty,
    State,
)
from plane.db.models.issue_type import ProjectIssueType
from plane.ext.services import ensure_project_system_types

ADMIN = 20

# `IssueView.access`: 0 is PRIVATE and 1 is PUBLIC -- the inverse of
# `Page.access`. Spelled out because a filter that confuses the two still looks
# correct.
VIEW_PRIVATE = 0
VIEW_PUBLIC = 1


def duplicate_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/duplicate/"


@pytest.fixture
def source_project(db, workspace, create_user):
    """A project with a representative amount of configuration in it."""
    project = Project.objects.create(
        name="Source Project",
        identifier="SRC",
        workspace=workspace,
        created_by=create_user,
        intake_view=True,
        cycle_view=True,
        module_view=True,
        is_time_tracking_enabled=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=ADMIN)
    # `ProjectSerializer.create` does this for a real project; the fixture builds
    # the row directly, so provision the workspace's system types by hand.
    ensure_project_system_types(project)

    backlog = State.objects.create(
        name="Backlog", color="#000", group="backlog", project=project, workspace=workspace, sequence=1000
    )
    State.objects.create(
        name="Done", color="#0f0", group="completed", project=project, workspace=workspace, sequence=2000
    )
    # Triage states are excluded by the default `State.objects` manager, which is
    # exactly why a copy must not use it.
    State.objects.create(
        name="Triage",
        color="#f00",
        group="triage",
        is_triage=True,
        project=project,
        workspace=workspace,
        sequence=3000,
    )

    parent_label = Label.objects.create(name="Area", project=project, workspace=workspace, sort_order=1)
    Label.objects.create(name="Area/API", project=project, workspace=workspace, parent=parent_label, sort_order=2)

    estimate = Estimate.objects.create(name="Points", project=project, workspace=workspace)
    EstimatePoint.objects.create(estimate=estimate, key=1, value="1", project=project, workspace=workspace)
    EstimatePoint.objects.create(estimate=estimate, key=2, value="2", project=project, workspace=workspace)

    Intake.objects.create(name="Source Intake", is_default=True, project=project, workspace=workspace)

    Cycle.objects.create(name="Sprint 1", owned_by=create_user, project=project, workspace=workspace)
    Module.objects.create(
        name="Onboarding",
        project=project,
        workspace=workspace,
        external_source="todoist_csv",
        external_id="mod-1",
    )

    project.default_state = backlog
    project.estimate = estimate
    project.save()
    return project


@pytest.mark.contract
@pytest.mark.django_db
class TestProjectDuplicate:
    def test_copies_configuration_and_leaves_the_source_alone(self, session_client, workspace, source_project):
        source_state_count = State.all_state_objects.filter(project=source_project, deleted_at__isnull=True).count()

        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id),
            {"include": {"cycles": True, "modules": True}},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        copy = Project.objects.get(pk=response.data["id"])
        assert copy.id != source_project.id

        # The triage state is the one a naive `State.objects` query drops.
        copied_states = State.all_state_objects.filter(project=copy, deleted_at__isnull=True)
        assert copied_states.count() == source_state_count
        assert copied_states.filter(is_triage=True).exists()

        assert Label.objects.filter(project=copy).count() == 2
        assert Estimate.objects.filter(project=copy).count() == 1
        assert EstimatePoint.objects.filter(project=copy).count() == 2
        assert Intake.objects.filter(project=copy).count() == 1
        assert Cycle.objects.filter(project=copy).count() == 1
        assert Module.objects.filter(project=copy).count() == 1

        # Feature toggles describe what the project is, so they travel.
        assert copy.is_time_tracking_enabled is True
        assert copy.intake_view is True

        # The source is untouched.
        source_project.refresh_from_db()
        assert source_project.name == "Source Project"
        assert State.all_state_objects.filter(project=source_project, deleted_at__isnull=True).count() == (
            source_state_count
        )

    def test_every_copied_row_belongs_to_the_new_workspace(self, session_client, workspace, source_project):
        """``bulk_create`` bypasses the ``save()`` that normally sets ``workspace``."""
        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id),
            {"include": {"cycles": True, "modules": True}},
            format="json",
        )
        copy = Project.objects.get(pk=response.data["id"])

        for model in (State, Label, Estimate, EstimatePoint, Intake, Cycle, Module, ProjectIssueType):
            manager = State.all_state_objects if model is State else model.objects
            rows = manager.filter(project=copy)
            assert rows.exists(), f"{model.__name__} copied nothing"
            assert not rows.exclude(workspace_id=copy.workspace_id).exists(), (
                f"{model.__name__} rows escaped the target workspace"
            )

    def test_project_foreign_keys_point_at_the_copy(self, session_client, workspace, source_project):
        response = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")
        copy = Project.objects.get(pk=response.data["id"])

        assert copy.default_state_id is not None
        assert copy.default_state.project_id == copy.id
        assert copy.estimate_id is not None
        assert copy.estimate.project_id == copy.id

        # The caller leads their own copy; the source's lead did not ask to.
        assert copy.project_lead_id is not None
        assert copy.default_assignee_id is None

    def test_label_hierarchy_is_remapped_into_the_copy(self, session_client, workspace, source_project):
        response = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")
        copy = Project.objects.get(pk=response.data["id"])

        child = Label.objects.get(project=copy, name="Area/API")
        assert child.parent is not None
        assert child.parent.project_id == copy.id, "label parent still points into the source project"

    def test_external_identifiers_are_cleared(self, session_client, workspace, source_project):
        """``todoist_module_external_uidx`` keys on these; copying them corrupts import dedup."""
        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id), {"include": {"modules": True}}, format="json"
        )
        copy = Project.objects.get(pk=response.data["id"])

        module = Module.objects.get(project=copy)
        assert module.external_source is None
        assert module.external_id is None
        assert copy.external_source is None
        assert copy.external_id is None

    def test_identifier_row_and_work_item_types_are_provisioned(self, session_client, workspace, source_project):
        types_before = IssueType.objects.filter(workspace=workspace).count()

        response = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")
        copy = Project.objects.get(pk=response.data["id"])

        assert ProjectIdentifier.objects.filter(project=copy, name=copy.identifier).exists()
        assert ProjectIssueType.objects.filter(project=copy).exists()
        # IssueType is workspace-scoped and uniquely keyed on (workspace,
        # system_key); the copy re-links, it does not clone.
        assert IssueType.objects.filter(workspace=workspace).count() == types_before

    def test_caller_becomes_an_admin_with_a_user_property(self, session_client, workspace, source_project, create_user):
        response = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")
        copy = Project.objects.get(pk=response.data["id"])

        membership = ProjectMember.objects.get(project=copy, member=create_user)
        assert membership.role == ADMIN
        # `ProjectMember.save()` creates this; `bulk_create` would not have.
        assert ProjectUserProperty.objects.filter(project=copy, user=create_user).exists()

    def test_members_are_not_copied_unless_asked_for(self, session_client, workspace, source_project):
        from plane.db.models import User, WorkspaceMember

        other = User.objects.create(email="teammate@example.test", username="teammate")
        other.set_password("test-password")
        other.save()
        WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
        ProjectMember.objects.create(project=source_project, member=other, workspace=workspace, role=15)

        default_copy = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")
        assert not ProjectMember.objects.filter(project_id=default_copy.data["id"], member=other).exists(), (
            "membership must be opt-in; copying it silently grants access"
        )

        opted_in = session_client.post(
            duplicate_url(workspace.slug, source_project.id), {"include": {"members": True}}, format="json"
        )
        assert ProjectMember.objects.filter(project_id=opted_in.data["id"], member=other).exists()

    def test_private_views_of_other_members_are_not_copied(self, session_client, workspace, source_project):
        from plane.db.models import User, WorkspaceMember

        other = User.objects.create(email="viewowner@example.test", username="viewowner")
        other.set_password("test-password")
        other.save()
        WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
        ProjectMember.objects.create(project=source_project, member=other, workspace=workspace, role=15)

        IssueView.objects.create(
            name="Their private view",
            access=VIEW_PRIVATE,
            owned_by=other,
            project=source_project,
            workspace=workspace,
            query={},
        )
        IssueView.objects.create(
            name="Shared view",
            access=VIEW_PUBLIC,
            owned_by=other,
            project=source_project,
            workspace=workspace,
            query={},
        )

        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id), {"include": {"views": True}}, format="json"
        )
        copied = IssueView.objects.filter(project_id=response.data["id"])

        assert copied.filter(name="Shared view").exists()
        assert not copied.filter(name="Their private view").exists()
        assert "views:private" in response.data["copy_summary"]["skipped"]

    def test_repeated_duplication_derives_free_names_and_identifiers(self, session_client, workspace, source_project):
        first = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")
        second = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_201_CREATED
        assert first.data["name"] == "Source Project (Copy)"
        assert second.data["name"] == "Source Project (Copy 2)"
        assert first.data["identifier"] != second.data["identifier"]

    def test_an_explicit_colliding_name_is_reported(self, session_client, workspace, source_project):
        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id), {"name": "Source Project"}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "PROJECT_NAME_ALREADY_EXIST"

    def test_an_unknown_copy_option_is_rejected(self, session_client, workspace, source_project):
        """The opt-in surface is a closed set, so a typo cannot silently do nothing."""
        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id), {"include": {"everything": True}}, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_an_archived_source_is_refused(self, session_client, workspace, source_project):
        from django.utils import timezone

        source_project.archived_at = timezone.now()
        source_project.save()

        response = session_client.post(duplicate_url(workspace.slug, source_project.id), {}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "PROJECT_ARCHIVED"

    def test_no_work_items_or_publication_state_are_copied(self, session_client, workspace, source_project):
        from plane.db.models import DeployBoard, Issue

        response = session_client.post(
            duplicate_url(workspace.slug, source_project.id),
            {"include": {"cycles": True, "modules": True}},
            format="json",
        )
        copy_id = response.data["id"]

        assert not Issue.objects.filter(project_id=copy_id).exists()
        assert not DeployBoard.objects.filter(project_id=copy_id).exists()
        assert "webhooks:not-copied" in response.data["copy_summary"]["skipped"]
