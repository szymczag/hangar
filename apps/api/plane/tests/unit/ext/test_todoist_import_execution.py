# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import csv
from io import StringIO

import pytest
from django.utils import timezone

from plane.db.models import Issue, IssueActivity, IssueComment, Module, ModuleIssue, Project, ProjectMember, State
from plane.ext.importers.todoist import ImportCancelled, execute_todoist_import
from plane.ext.models import ImportJob
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
        preview = parse_todoist_csv(content)
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_key="private/import.csv",
            source_digest=preview.digest,
            source_size=len(content),
            config={"assignee_mapping": {"Owner (100)": str(create_user.id)}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        stats, diagnostics = execute_todoist_import(job)

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
        preview = parse_todoist_csv(content)
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_key="private/import.csv",
            source_digest=preview.digest,
            source_size=len(content),
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        stats, diagnostics = execute_todoist_import(job)

        import_project.refresh_from_db()
        assert import_project.description == "Existing context"
        assert stats["skipped"] == 1
        assert "project_note_not_overwritten" in [item["code"] for item in diagnostics]

    def test_digest_mismatch_fails_before_writing(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_key="private/import.csv",
            source_digest="0" * 64,
            source_size=len(content),
            config={},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        with pytest.raises(Exception, match="source_digest_mismatch"):
            execute_todoist_import(job)

        assert Issue.objects.filter(project=import_project).count() == 0

    def test_retry_is_idempotent_for_created_entities(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        preview = parse_todoist_csv(content)
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_key="private/import.csv",
            source_digest=preview.digest,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        execute_todoist_import(job)
        entity_counts = (
            Issue.objects.filter(project=import_project).count(),
            Module.objects.filter(project=import_project).count(),
            IssueComment.objects.filter(project=import_project).count(),
            IssueActivity.objects.filter(project=import_project).count(),
        )
        execute_todoist_import(job)

        assert entity_counts == (2, 1, 2, 4)
        assert (
            Issue.objects.filter(project=import_project).count(),
            Module.objects.filter(project=import_project).count(),
            IssueComment.objects.filter(project=import_project).count(),
            IssueActivity.objects.filter(project=import_project).count(),
        ) == entity_counts

    def test_unexpected_row_failure_propagates_for_task_retry(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        preview = parse_todoist_csv(content)
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_key="private/import.csv",
            source_digest=preview.digest,
            config={"assignee_mapping": {}, "module_conflicts": {}},
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)
        mocker.patch("plane.ext.importers.todoist._create_issue", side_effect=RuntimeError("database unavailable"))

        with pytest.raises(RuntimeError, match="database unavailable"):
            execute_todoist_import(job)

    def test_processing_cancellation_stops_before_next_batch(self, mocker, workspace, create_user, import_project):
        content = import_csv()
        preview = parse_todoist_csv(content)
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_key="private/import.csv",
            source_digest=preview.digest,
            config={"assignee_mapping": {}, "module_conflicts": {}},
            cancel_requested_at=timezone.now(),
        )
        mocker.patch("plane.ext.importers.todoist.read_import_source", return_value=content)

        with pytest.raises(ImportCancelled):
            execute_todoist_import(job)

        assert Issue.objects.filter(project=import_project).count() == 0
