# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.utils import timezone

from plane.db.models import Project, ProjectMember, State, WorkspaceMember
from plane.ext.importers.todoist import ImportCancelled
from plane.ext.imports.services import (
    ImportLeaseLost,
    ImportQuotaExceeded,
    ImportRetryMismatch,
    claim_execution,
    fail_preparing_job,
    finish_execution,
    lease_duration,
    mark_source_stored,
    recover_expired_execution,
    release_quota_once,
    request_cancellation,
    reserve_job,
)
from plane.ext.models import (
    ImportAuditEvent,
    ImportDispatch,
    ImportJob,
    ImportUserBudget,
    ImportWorkspaceBudget,
)
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

    def test_todoist_task_routes_only_to_dedicated_queue(self):
        from plane.celery import app

        assert app.conf.task_routes["plane.ext.tasks.run_todoist_import"] == {"queue": "imports"}

    def test_out_of_range_runtime_setting_fails_closed(self, settings):
        settings.TODOIST_IMPORT_LEASE_SECONDS = 10

        with pytest.raises(ImproperlyConfigured, match="between 30 and 900"):
            lease_duration()

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
        assert (
            claim_execution(
                job_id=job.id,
                generation=claim.generation,
                task_id=str(claim.task_id),
            )
            is None
        )
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

    def test_claim_fails_closed_after_admin_revocation(self, queued_job, workspace, create_user):
        job, dispatch = queued_job(digest="3" * 64)
        WorkspaceMember.objects.filter(
            workspace=workspace,
            member=create_user,
        ).update(is_active=False)

        claim = claim_execution(
            job_id=job.id,
            generation=dispatch.generation,
            task_id=str(dispatch.task_id),
        )

        assert claim is None
        job.refresh_from_db()
        dispatch.refresh_from_db()
        assert job.status == ImportJob.Status.FAILED
        assert job.reason == "authorization_revoked"
        assert job.config == {}
        assert dispatch.state == ImportDispatch.State.SUPERSEDED
        assert ImportAuditEvent.objects.filter(
            job_id=job.id,
            action=ImportAuditEvent.Action.AUTHORIZATION_REVOKED,
        ).exists()

    def test_exact_retry_creates_new_job_with_original_namespace(
        self,
        workspace,
        create_user,
        import_project,
    ):
        config = {"assignee_mapping": {}, "module_conflicts": {}}
        failed = reserve_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="4" * 64,
            source_size=128,
            config=config,
            stats={},
            errors=[],
        )
        fail_preparing_job(job_id=failed.id, reason="source_store_failed")

        retry = reserve_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="4" * 64,
            source_size=128,
            config=config,
            stats={},
            errors=[],
            retry_of_id=failed.id,
        )

        assert retry.id != failed.id
        assert retry.retry_of_id == failed.id
        assert retry.idempotency_namespace == failed.idempotency_namespace
        failed.refresh_from_db()
        assert failed.status == ImportJob.Status.FAILED

    def test_changed_retry_manifest_cannot_inherit_namespace(
        self,
        workspace,
        create_user,
        import_project,
    ):
        failed = reserve_job(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="5" * 64,
            source_size=128,
            config={"assignee_mapping": {}, "module_conflicts": {}},
            stats={},
            errors=[],
        )
        fail_preparing_job(job_id=failed.id, reason="source_store_failed")

        with pytest.raises(ImportRetryMismatch):
            reserve_job(
                workspace=workspace,
                project=import_project,
                initiated_by=create_user,
                source_digest="5" * 64,
                source_size=128,
                config={"assignee_mapping": {"changed": str(create_user.id)}},
                stats={},
                errors=[],
                retry_of_id=failed.id,
            )

        assert ImportJob.objects.filter(retry_of=failed).count() == 0

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
        assert ImportWorkspaceBudget.objects.get(workspace=finished_job.workspace).active_jobs == 0
        assert (
            ImportUserBudget.objects.get(
                workspace=finished_job.workspace,
                user=create_user,
            ).active_jobs
            == 0
        )

        with pytest.raises(ImportLeaseLost):
            finish_execution(
                job_id=job.id,
                generation=claim.generation,
                lease_token=claim.lease_token,
                status=ImportJob.Status.COMPLETED,
            )
        assert ImportWorkspaceBudget.objects.get(workspace=finished_job.workspace).active_jobs == 0

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

    def test_admission_usage_rejects_application_mutation(self, queued_job):
        job, _ = queued_job(digest="4" * 64)
        usage = job.admission_usage

        usage.source_rows = 999
        with pytest.raises(ValidationError):
            usage.save()
        with pytest.raises(ValidationError):
            type(usage).objects.filter(pk=usage.id).update(source_rows=999)
        with pytest.raises(ValidationError):
            usage.delete()


@pytest.mark.unit
@pytest.mark.todoist_migrations
@pytest.mark.django_db(transaction=True)
def test_audit_events_reject_database_mutation(workspace, create_user, import_project, request):
    if request.config.getoption("nomigrations") or "django_migrations" not in connection.introspection.table_names():
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


@pytest.mark.unit
@pytest.mark.todoist_migrations
@pytest.mark.django_db(transaction=True)
def test_todoist_idempotency_indexes_are_unique_and_partial(request):
    if request.config.getoption("nomigrations") or "django_migrations" not in connection.introspection.table_names():
        pytest.skip("database index test requires pytest --migrations")

    expected = {
        "todoist_issue_external_uidx": "issues",
        "todoist_comment_external_uidx": "issue_comments",
        "todoist_module_external_uidx": "modules",
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE indexname = ANY(%s)
            """,
            [list(expected)],
        )
        indexes = {name: (table, definition) for name, table, definition in cursor.fetchall()}

    assert set(indexes) == set(expected)
    for name, table in expected.items():
        actual_table, definition = indexes[name]
        assert actual_table == table
        assert "CREATE UNIQUE INDEX" in definition
        assert "deleted_at IS NULL" in definition
        assert "external_source" in definition and "todoist_csv" in definition
        assert "external_id IS NOT NULL" in definition


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
def test_concurrent_reservations_enforce_user_limit_atomically(settings, workspace, create_user):
    settings.TODOIST_IMPORT_MAX_ACTIVE_PER_USER = 1
    settings.TODOIST_IMPORT_MAX_ACTIVE_PER_WORKSPACE = 2
    projects = [
        Project.objects.create(
            name=f"Concurrent import {index}",
            identifier=f"CI{index}",
            workspace=workspace,
        )
        for index in range(2)
    ]
    barrier = Barrier(2)

    def reserve(project_id):
        close_old_connections()
        try:
            barrier.wait()
            return reserve_job(
                workspace=type(workspace).objects.get(pk=workspace.id),
                project=Project.objects.get(pk=project_id),
                initiated_by=type(create_user).objects.get(pk=create_user.id),
                source_digest=str(project_id).replace("-", "") * 2,
                source_size=128,
                config={},
                stats={"source_rows": 1},
                errors=[],
            ).id
        except ImportQuotaExceeded as error:
            return error.limit
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(reserve, [project.id for project in projects]))

    assert results.count("active_user_imports") == 1
    assert ImportJob.objects.filter(status=ImportJob.Status.PREPARING).count() == 1
    assert ImportWorkspaceBudget.objects.get(workspace=workspace).active_jobs == 1
    assert ImportUserBudget.objects.get(workspace=workspace, user=create_user).active_jobs == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_workspace_active_limit_applies_across_users(settings, workspace, create_user):
    settings.TODOIST_IMPORT_MAX_ACTIVE_PER_WORKSPACE = 1
    second_user = type(create_user).objects.create(
        email=f"second-{uuid4().hex}@hangar.test",
        username=f"second-{uuid4().hex}@hangar.test",
    )
    projects = [
        Project.objects.create(name=f"Workspace limit {index}", identifier=f"WL{index}", workspace=workspace)
        for index in range(2)
    ]
    reserve_job(
        workspace=workspace,
        project=projects[0],
        initiated_by=create_user,
        source_digest="1" * 64,
        source_size=128,
        config={},
        stats={"source_rows": 1},
        errors=[],
    )

    with pytest.raises(ImportQuotaExceeded) as error:
        reserve_job(
            workspace=workspace,
            project=projects[1],
            initiated_by=second_user,
            source_digest="2" * 64,
            source_size=128,
            config={},
            stats={"source_rows": 1},
            errors=[],
        )

    assert error.value.limit == "active_workspace_imports"
    assert ImportWorkspaceBudget.objects.get(workspace=workspace).active_jobs == 1


@pytest.mark.unit
@pytest.mark.django_db
def test_workspace_source_byte_limit_is_reserved_atomically(settings, workspace, create_user):
    settings.TODOIST_IMPORT_MAX_ACTIVE_SOURCE_BYTES_PER_WORKSPACE = 200
    second_user = type(create_user).objects.create(
        email=f"source-{uuid4().hex}@hangar.test",
        username=f"source-{uuid4().hex}@hangar.test",
    )
    projects = [
        Project.objects.create(name=f"Source limit {index}", identifier=f"SL{index}", workspace=workspace)
        for index in range(2)
    ]
    reserve_job(
        workspace=workspace,
        project=projects[0],
        initiated_by=create_user,
        source_digest="3" * 64,
        source_size=128,
        config={},
        stats={"source_rows": 1},
        errors=[],
    )

    with pytest.raises(ImportQuotaExceeded) as error:
        reserve_job(
            workspace=workspace,
            project=projects[1],
            initiated_by=second_user,
            source_digest="4" * 64,
            source_size=100,
            config={},
            stats={"source_rows": 1},
            errors=[],
        )

    assert error.value.limit == "active_workspace_source_bytes"
    budget = ImportWorkspaceBudget.objects.get(workspace=workspace)
    assert budget.active_jobs == 1
    assert budget.active_source_bytes == 128


@pytest.mark.unit
@pytest.mark.django_db
def test_quota_release_is_exactly_once(workspace, create_user, import_project):
    job = reserve_job(
        workspace=workspace,
        project=import_project,
        initiated_by=create_user,
        source_digest="5" * 64,
        source_size=128,
        config={},
        stats={"source_rows": 1},
        errors=[],
    )

    assert release_quota_once(job_id=job.id) is True
    assert release_quota_once(job_id=job.id) is False

    job.refresh_from_db()
    workspace_budget = ImportWorkspaceBudget.objects.get(workspace=workspace)
    user_budget = ImportUserBudget.objects.get(workspace=workspace, user=create_user)
    assert job.quota_released_at is not None
    assert workspace_budget.active_jobs == 0
    assert workspace_budget.active_source_bytes == 0
    assert user_budget.active_jobs == 0
