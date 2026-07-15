# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from plane.db.models import Project, ProjectMember, State
from plane.ext.importers.todoist import ImportCancelled
from plane.ext.imports.services import (
    ImportLeaseLost,
    claim_execution,
    finish_execution,
    mark_source_stored,
    recover_expired_execution,
    request_cancellation,
    reserve_job,
)
from plane.ext.models import ImportAuditEvent, ImportDispatch, ImportJob
from plane.ext.tasks import run_todoist_import


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


@pytest.fixture
def queued_job(workspace, create_user, import_project):
    def create(*, digest="a" * 64, source_key="imports/source.csv", config=None):
        job = reserve_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest=digest,
            source_size=128,
            config=config or {},
            stats={},
            errors=[],
        )
        return mark_source_stored(job_id=job.id, source_key=source_key)

    return create


@pytest.mark.unit
@pytest.mark.django_db
class TestTodoistImportTask:
    @pytest.fixture(autouse=True)
    def enable_todoist_imports(self, settings):
        settings.TODOIST_IMPORTS_ENABLED = True

    def test_disabled_importer_does_not_claim_or_mutate_job(self, mocker, settings, queued_job):
        settings.TODOIST_IMPORTS_ENABLED = False
        job, dispatch = queued_job(digest="d" * 64)
        execute = mocker.patch("plane.ext.tasks.execute_todoist_import")

        run_todoist_import.apply(
            args=[str(job.id), dispatch.generation],
            task_id=str(dispatch.task_id),
        )

        job.refresh_from_db()
        dispatch.refresh_from_db()
        assert job.status == ImportJob.Status.QUEUED
        assert job.attempt_count == 0
        assert dispatch.state == ImportDispatch.State.PENDING
        execute.assert_not_called()

    def test_expired_lease_recovery_fences_the_old_worker(self, settings, queued_job):
        settings.TODOIST_IMPORT_RECOVERY_GRACE_SECONDS = 0
        job, dispatch = queued_job(digest="c" * 64)
        claim = claim_execution(
            job_id=job.id,
            generation=dispatch.generation,
            task_id=str(dispatch.task_id),
        )
        assert claim is not None
        ImportJob.objects.filter(pk=job.id).update(lease_expires_at=timezone.now() - timedelta(seconds=1))

        recovered_dispatch = recover_expired_execution(job_id=job.id)

        assert recovered_dispatch is not None
        job.refresh_from_db()
        assert job.status == ImportJob.Status.QUEUED
        assert job.execution_generation == 1
        assert job.lease_token is None
        assert claim_execution(
            job_id=job.id,
            generation=claim.generation,
            task_id=str(claim.task_id),
        ) is None
        assert ImportAuditEvent.objects.filter(
            job_id=job.id,
            action=ImportAuditEvent.Action.LEASE_RECOVERED,
        ).exists()

        with pytest.raises(ImportLeaseLost):
            finish_execution(
                job_id=job.id,
                generation=claim.generation,
                lease_token=claim.lease_token,
                status=ImportJob.Status.COMPLETED,
            )
        job.refresh_from_db()
        assert job.status == ImportJob.Status.QUEUED

    def test_partial_result_has_honest_terminal_status(self, mocker, queued_job):
        job, dispatch = queued_job(config={"assignee_mapping": {}})
        mocker.patch(
            "plane.ext.tasks.execute_todoist_import",
            return_value=({"failed": 1, "imported_tasks": 2}, [{"code": "invalid_task"}]),
        )
        mocker.patch("plane.ext.tasks.delete_import_source", return_value=True)

        run_todoist_import.apply(
            args=[str(job.id), dispatch.generation],
            task_id=str(dispatch.task_id),
        )

        job.refresh_from_db()
        assert job.status == ImportJob.Status.COMPLETED_WITH_ERRORS
        assert job.attempt_count == 1
        assert job.config == {}
        assert job.source_key == ""
        assert job.lease_token is None

    def test_cooperative_cancel_is_terminal_and_cleans_source(self, mocker, queued_job):
        job, dispatch = queued_job(digest="b" * 64)
        mocker.patch("plane.ext.tasks.execute_todoist_import", side_effect=ImportCancelled)
        mocker.patch("plane.ext.tasks.delete_import_source", return_value=True)

        run_todoist_import.apply(
            args=[str(job.id), dispatch.generation],
            task_id=str(dispatch.task_id),
        )

        job.refresh_from_db()
        assert job.status == ImportJob.Status.CANCELLED
        assert job.reason == "cancelled_by_user"
        assert job.source_key == ""

    def test_duplicate_delivery_is_a_noop_while_execution_is_leased(self, queued_job):
        job, dispatch = queued_job()
        first = claim_execution(
            job_id=job.id,
            generation=dispatch.generation,
            task_id=str(dispatch.task_id),
        )

        duplicate = claim_execution(
            job_id=job.id,
            generation=dispatch.generation,
            task_id=str(dispatch.task_id),
        )

        assert first is not None
        assert duplicate is None

    def test_cancellation_wins_over_worker_completion(self, queued_job, create_user):
        job, dispatch = queued_job(digest="e" * 64)
        claim = claim_execution(
            job_id=job.id,
            generation=dispatch.generation,
            task_id=str(dispatch.task_id),
        )
        assert claim is not None

        cancelling_job, terminal = request_cancellation(
            job_id=job.id,
            actor_id=create_user.id,
        )
        assert terminal is False
        assert cancelling_job.status == ImportJob.Status.CANCELLING

        finished_job = finish_execution(
            job_id=job.id,
            generation=claim.generation,
            lease_token=claim.lease_token,
            status=ImportJob.Status.COMPLETED,
        )

        assert finished_job.status == ImportJob.Status.CANCELLED
        assert finished_job.reason == "cancelled_by_user"
        assert finished_job.lease_token is None
        assert finished_job.completed_at is not None

    def test_wrong_lease_token_cannot_finish_execution(self, queued_job):
        job, dispatch = queued_job(digest="f" * 64)
        claim = claim_execution(
            job_id=job.id,
            generation=dispatch.generation,
            task_id=str(dispatch.task_id),
        )
        assert claim is not None

        with pytest.raises(ImportLeaseLost):
            finish_execution(
                job_id=job.id,
                generation=claim.generation,
                lease_token=uuid4(),
                status=ImportJob.Status.COMPLETED,
            )

        job.refresh_from_db()
        assert job.status == ImportJob.Status.PROCESSING
        assert job.lease_token == claim.lease_token

    def test_audit_events_reject_application_mutation(self, queued_job):
        job, _ = queued_job(digest="1" * 64)
        event = ImportAuditEvent.objects.filter(job_id=job.id).first()
        assert event is not None

        event.action = ImportAuditEvent.Action.CLEANUP_FAILED
        with pytest.raises(ValidationError):
            event.save()
        with pytest.raises(ValidationError):
            ImportAuditEvent.objects.filter(pk=event.id).update(action=ImportAuditEvent.Action.CLEANUP_FAILED)
        with pytest.raises(ValidationError):
            event.delete()


@pytest.mark.unit
@pytest.mark.todoist_migrations
@pytest.mark.django_db(transaction=True)
def test_audit_events_reject_database_mutation(workspace, create_user, import_project, request):
    if (
        request.config.getoption("nomigrations")
        or "django_migrations" not in connection.introspection.table_names()
    ):
        pytest.skip("database trigger test requires pytest --migrations")
    job = reserve_job(
        workspace=workspace,
        project=import_project,
        initiated_by=create_user,
        source_digest="2" * 64,
        source_size=128,
        config={},
        stats={},
        errors=[],
    )
    event = ImportAuditEvent.objects.get(job_id=job.id)

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE ext_import_audit_events SET action = %s WHERE id = %s",
                [ImportAuditEvent.Action.CLEANUP_FAILED, event.id],
            )

    event.refresh_from_db()
    assert event.action == ImportAuditEvent.Action.CREATED
