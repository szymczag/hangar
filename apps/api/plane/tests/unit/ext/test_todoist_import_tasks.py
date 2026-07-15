# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Project, ProjectMember, State
from plane.ext.importers.todoist import ImportCancelled
from plane.ext.models import ImportJob
from plane.ext.tasks import _claim_job, run_todoist_import


@pytest.fixture
def import_project(db, workspace, create_user):
    project = Project.objects.create(name="Import Project", identifier="IMP", workspace=workspace)
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
class TestTodoistImportTask:
    @pytest.fixture(autouse=True)
    def enable_todoist_imports(self, settings):
        settings.TODOIST_IMPORTS_ENABLED = True

    def test_disabled_importer_does_not_claim_or_mutate_job(
        self, mocker, settings, workspace, create_user, import_project
    ):
        settings.TODOIST_IMPORTS_ENABLED = False
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="d" * 64,
            status=ImportJob.Status.QUEUED,
            celery_task_id="disabled-task",
        )
        execute = mocker.patch("plane.ext.tasks.execute_todoist_import")

        run_todoist_import.run(str(job.id))

        job.refresh_from_db()
        assert job.status == ImportJob.Status.QUEUED
        assert job.attempt_count == 0
        execute.assert_not_called()

    def test_broker_redelivery_recovers_job_after_worker_loss(self, workspace, create_user, import_project):
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="c" * 64,
            status=ImportJob.Status.PROCESSING,
            celery_task_id="worker-task",
            attempt_count=1,
        )

        claimed = _claim_job(str(job.id), "worker-task", redelivered=True)

        assert claimed is not None
        assert claimed.attempt_count == 2

    def test_partial_result_has_honest_terminal_status(self, mocker, workspace, create_user, import_project):
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="a" * 64,
            source_key="imports/source.csv",
            status=ImportJob.Status.QUEUED,
            config={"assignee_mapping": {}},
        )
        mocker.patch(
            "plane.ext.tasks.execute_todoist_import",
            return_value=({"failed": 1, "imported_tasks": 2}, [{"code": "invalid_task"}]),
        )
        mocker.patch("plane.ext.tasks.delete_import_source", return_value=True)

        run_todoist_import.run(str(job.id))

        job.refresh_from_db()
        assert job.status == ImportJob.Status.COMPLETED_WITH_ERRORS
        assert job.attempt_count == 1
        assert job.config == {}
        assert job.source_key == ""

    def test_cooperative_cancel_is_terminal_and_cleans_source(self, mocker, workspace, create_user, import_project):
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="b" * 64,
            source_key="imports/source.csv",
            status=ImportJob.Status.QUEUED,
        )
        mocker.patch("plane.ext.tasks.execute_todoist_import", side_effect=ImportCancelled)
        mocker.patch("plane.ext.tasks.delete_import_source", return_value=True)

        run_todoist_import.run(str(job.id))

        job.refresh_from_db()
        assert job.status == ImportJob.Status.CANCELLED
        assert job.reason == "cancelled_by_user"
        assert job.source_key == ""
