# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import csv
from io import StringIO

import pytest
import plane.ext.importers.todoist as todoist_importer
from plane.db.models import (
    Issue,
    IssueActivity,
    IssueComment,
    Module,
    ModuleIssue,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)
from plane.ext.importers.todoist import execute_todoist_import
from plane.ext.imports import (
    ImportAuthorizationRevoked,
    ImportCancellationRequested,
    ImportDecisionDrift,
)
from plane.ext.imports.services import claim_execution, mark_source_stored, request_cancellation, reserve_job
from plane.ext.utils.importers.todoist_csv import parse_todoist_csv


HEADERS = [
    "TYPE",
    "CONTENT",
    "DESCRIPTION",
    "IS_COLLAPSED",
    "PRIORITY",
    "INDENT",
    "AUTHOR",
    "RESPONSIBLE",
    "DATE",
    "DATE_LANG",
    "TIMEZONE",
    "DURATION",
    "DURATION_UNIT",
    "DEADLINE",
    "DEADLINE_LANG",
]


def import_csv() -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerows(
        [
            {"TYPE": "project_note", "CONTENT": "Imported project context"},
            {"TYPE": "section", "CONTENT": "Imported section"},
            {
                "TYPE": "task",
                "CONTENT": "Parent task",
                "DESCRIPTION": "Parent **description**",
                "PRIORITY": "1",
                "INDENT": "1",
                "RESPONSIBLE": "Owner (100)",
                "DATE": "2026-07-20",
                "DEADLINE": "2026-07-25",
            },
            {"TYPE": "note", "CONTENT": "Imported task comment"},
            {
                "TYPE": "task",
                "CONTENT": "Child task",
                "PRIORITY": "4",
                "INDENT": "2",
                "DATE": "every Monday",
                "TIMEZONE": "Europe/Warsaw",
            },
        ]
    )
    return output.getvalue().encode()


def claimed_import_job(*, workspace, project, initiated_by, content, config):
    preview = parse_todoist_csv(content)
    job = reserve_job(
        workspace=workspace,
        project=project,
        initiated_by=initiated_by,
        source_digest=preview.digest,
        source_size=len(content),
        config=config,
        stats={},
        errors=[],
    )
    job, dispatch = mark_source_stored(job_id=job.id, source_key="private/import.csv")
    claim = claim_execution(
        job_id=job.id,
        generation=dispatch.generation,
        task_id=str(dispatch.task_id),
    )
    assert claim is not None
    return claim


@pytest.fixture
def import_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Import Project",
        identifier="IMP",
        workspace=workspace,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    State.objects.create(
        name="Todo",
        group="unstarted",
        color="#4f46e5",
        project=project,
        workspace=workspace,
        default=True,
    )
    return project


@pytest.mark.unit
@pytest.mark.django_db
class TestTodoistImportExecution:
    def test_creates_project_structure_and_preserves_metadata(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {"Owner (100)": str(create_user.id)}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        stats, diagnostics = execute_todoist_import(
            claim.job,
            generation=claim.generation,
            lease_token=claim.lease_token,
        )

        assert stats["imported_tasks"] == 2, diagnostics
        assert stats["imported_sections"] == 1
        assert stats["imported_notes"] == 1
        assert stats["failed"] == 0
        assert [item["code"] for item in diagnostics] == ["unsupported_schedule"]

        parent = Issue.objects.get(project=import_project, name="Parent task")
        child = Issue.objects.get(project=import_project, name="Child task")
        module = Module.objects.get(project=import_project, name="Imported section")
        import_project.refresh_from_db()

        assert parent.priority == "urgent"
        assert parent.start_date.isoformat() == "2026-07-20"
        assert parent.target_date.isoformat() == "2026-07-25"
        assert list(parent.assignees.values_list("id", flat=True)) == [create_user.id]
        assert child.parent_id == parent.id
        assert child.target_date is None
        assert ModuleIssue.objects.filter(module=module, issue__in=[parent, child]).count() == 2
        assert IssueComment.objects.filter(issue=parent, comment_html__contains="Imported task comment").exists()
        assert IssueComment.objects.filter(issue=child, comment_html__contains="Original schedule").exists()
        assert IssueComment.objects.filter(issue=child, comment_html__contains="Europe/Warsaw").exists()
        assert import_project.module_view is True
        assert import_project.description == "Imported project context"

    def test_existing_project_description_is_not_overwritten(self, mocker, workspace, create_user, import_project):
        import_project.description = "Existing context"
        import_project.save(update_fields=["description"])
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        stats, diagnostics = execute_todoist_import(
            claim.job,
            generation=claim.generation,
            lease_token=claim.lease_token,
        )

        import_project.refresh_from_db()
        assert import_project.description == "Existing context"
        assert stats["skipped"] == 1
        assert "project_note_not_overwritten" in [item["code"] for item in diagnostics]

    def test_digest_mismatch_fails_before_writing(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={},
        )
        claim.job.source_digest = "0" * 64
        claim.job.save(update_fields=["source_digest", "updated_at"])
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        with pytest.raises(Exception, match="source_digest_mismatch"):
            execute_todoist_import(
                claim.job,
                generation=claim.generation,
                lease_token=claim.lease_token,
            )

        assert Issue.objects.filter(project=import_project).count() == 0

    def test_retry_is_idempotent_for_created_entities(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        execute_todoist_import(claim.job, generation=claim.generation, lease_token=claim.lease_token)
        entity_counts = (
            Issue.objects.filter(project=import_project).count(),
            Module.objects.filter(project=import_project).count(),
            IssueComment.objects.filter(project=import_project).count(),
            IssueActivity.objects.filter(project=import_project).count(),
        )
        second_stats, _ = execute_todoist_import(
            claim.job,
            generation=claim.generation,
            lease_token=claim.lease_token,
        )

        assert entity_counts == (2, 1, 2, 4)
        assert (
            Issue.objects.filter(project=import_project).count(),
            Module.objects.filter(project=import_project).count(),
            IssueComment.objects.filter(project=import_project).count(),
            IssueActivity.objects.filter(project=import_project).count(),
        ) == entity_counts
        assert second_stats["imported_tasks"] == 0
        assert second_stats["reused_tasks"] == 2
        assert second_stats["reused_sections"] == 1
        assert second_stats["reused_notes"] == 1
        assert second_stats["reused_metadata_comments"] == 1

    def test_unexpected_row_failure_propagates_for_task_retry(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)
        mocker.patch("plane.ext.importers.todoist._create_issue", side_effect=RuntimeError("database unavailable"))

        with pytest.raises(RuntimeError, match="database unavailable"):
            execute_todoist_import(
                claim.job,
                generation=claim.generation,
                lease_token=claim.lease_token,
            )

    def test_processing_cancellation_stops_before_next_batch(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        request_cancellation(job_id=claim.job.id, actor_id=create_user.id)
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        with pytest.raises(ImportCancellationRequested):
            execute_todoist_import(
                claim.job,
                generation=claim.generation,
                lease_token=claim.lease_token,
            )

        assert Issue.objects.filter(project=import_project).count() == 0

    def test_manifest_drift_stops_before_any_mutation(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        claim.job.config = {"assignee_mapping": {"tampered": str(create_user.id)}}
        claim.job.save(update_fields=["config", "updated_at"])
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        with pytest.raises(ImportDecisionDrift):
            execute_todoist_import(
                claim.job,
                generation=claim.generation,
                lease_token=claim.lease_token,
            )

        import_project.refresh_from_db()
        assert import_project.module_view is False
        assert import_project.description == ""
        assert Issue.objects.filter(project=import_project).count() == 0
        assert Module.objects.filter(project=import_project).count() == 0

    def test_admin_revocation_between_rows_stops_later_writes(
        self,
        mocker,
        workspace,
        create_user,
        import_project,
    ):
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)
        original_create_issue = todoist_importer._create_issue
        revoked = False

        def revoke_after_guard(job, record, parent):
            nonlocal revoked
            if not revoked:
                WorkspaceMember.objects.filter(
                    workspace=workspace,
                    member=create_user,
                ).update(is_active=False)
                revoked = True
            return original_create_issue(job, record, parent)

        mocker.patch(
            "plane.ext.importers.todoist._create_issue",
            side_effect=revoke_after_guard,
        )

        with pytest.raises(ImportAuthorizationRevoked):
            execute_todoist_import(
                claim.job,
                generation=claim.generation,
                lease_token=claim.lease_token,
            )

        assert list(Issue.objects.filter(project=import_project).values_list("name", flat=True)) == ["Parent task"]
        assert IssueComment.objects.filter(project=import_project).count() == 0

    def test_inactive_mapped_assignee_fails_the_complete_source_row(
        self,
        mocker,
        workspace,
        create_user,
        import_project,
    ):
        assignee = User.objects.create(
            email="disabled-assignee@example.com",
            username="disabled-assignee",
            is_active=True,
        )
        ProjectMember.objects.create(
            project=import_project,
            member=assignee,
            role=15,
            is_active=True,
        )
        content = import_csv()
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={
                "assignee_mapping": {"Owner (100)": str(assignee.id)},
                "module_conflicts": {},
            },
        )
        assignee.is_active = False
        assignee.save(update_fields=["is_active", "updated_at"])
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        stats, diagnostics = execute_todoist_import(
            claim.job,
            generation=claim.generation,
            lease_token=claim.lease_token,
        )

        assert Issue.objects.filter(project=import_project).count() == 0
        assert stats["failed"] == 3
        assert "assignee_no_longer_eligible" in [item["code"] for item in diagnostics]

    def test_reused_module_decision_drift_fails_closed(
        self,
        mocker,
        workspace,
        create_user,
        import_project,
    ):
        existing_module = Module.objects.create(
            name="Imported section",
            project=import_project,
            status="planned",
        )
        content = import_csv()
        section = next(record for record in parse_todoist_csv(content).records if record.kind == "section")
        claim = claimed_import_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            content=content,
            config={
                "assignee_mapping": {},
                "module_conflicts": {
                    str(section.row): {
                        "action": "reuse",
                        "module_id": str(existing_module.id),
                        "expected_name": existing_module.name,
                        "expected_status": existing_module.status,
                        "expected_archived_at": None,
                    }
                },
            },
        )
        existing_module.status = "paused"
        existing_module.save(update_fields=["status", "updated_at"])
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        stats, diagnostics = execute_todoist_import(
            claim.job,
            generation=claim.generation,
            lease_token=claim.lease_token,
        )

        assert Issue.objects.filter(project=import_project).count() == 0
        assert stats["failed"] >= 1
        assert "module_decision_stale" in [item["code"] for item in diagnostics]
