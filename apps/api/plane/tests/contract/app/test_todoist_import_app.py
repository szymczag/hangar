# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import csv
import json
from io import StringIO
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Module, Project, ProjectMember, User, Workspace, WorkspaceMember
from plane.ext.models import ImportJob
from plane.ext.utils.importers.todoist_csv import parse_todoist_csv


HEADERS = [
    "TYPE",
    "CONTENT",
    "DESCRIPTION",
    "PRIORITY",
    "INDENT",
    "RESPONSIBLE",
    "DATE",
    "DEADLINE",
]


def csv_content() -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerow(
        {
            "TYPE": "task",
            "CONTENT": "Synthetic task",
            "DESCRIPTION": "Synthetic description",
            "PRIORITY": "4",
            "INDENT": "1",
            "RESPONSIBLE": "Owner (100)",
        }
    )
    return output.getvalue().encode()


def section_csv(name: str) -> bytes:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerow({"TYPE": "section", "CONTENT": name})
    return output.getvalue().encode()


def upload(content: bytes | None = None, *, content_type: str = "text/csv") -> SimpleUploadedFile:
    return SimpleUploadedFile("template.csv", content or csv_content(), content_type=content_type)


@pytest.fixture
def import_project(db, workspace, create_user):
    project = Project.objects.create(
        name="Import Project",
        identifier="IMP",
        workspace=workspace,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


def preview_url(workspace):
    return f"/api/workspaces/{workspace.slug}/imports/todoist/preview/"


def import_url(workspace):
    return f"/api/workspaces/{workspace.slug}/imports/todoist/"


@pytest.mark.contract
@pytest.mark.django_db
class TestTodoistImportAPI:
    @pytest.fixture(autouse=True)
    def enable_todoist_imports(self, settings):
        settings.TODOIST_IMPORTS_ENABLED = True

    def test_disabled_importer_fails_closed_before_parsing(
        self, mocker, settings, session_client, workspace, import_project
    ):
        settings.TODOIST_IMPORTS_ENABLED = False
        parse_upload = mocker.patch("plane.ext.views.import_job._parse_upload")

        response = session_client.post(
            preview_url(workspace),
            {"project_id": str(import_project.id), "file": upload()},
            format="multipart",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["code"] == "importer_disabled"
        parse_upload.assert_not_called()
        assert ImportJob.objects.count() == 0

    def test_execute_requires_valid_csrf_token(self, workspace, import_project, create_user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(create_user)
        content = csv_content()
        payload = {
            "project_id": str(import_project.id),
            "preview_digest": parse_todoist_csv(content).digest,
            "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
            "file": upload(content),
        }

        rejected = client.post(import_url(workspace), payload, format="multipart")

        assert rejected.status_code == status.HTTP_403_FORBIDDEN
        assert ImportJob.objects.count() == 0

    def test_execute_accepts_valid_csrf_token(self, mocker, workspace, import_project, create_user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(create_user)
        csrf_response = client.get("/auth/get-csrf-token/")
        csrf_token = csrf_response.data["csrf_token"]
        content = csv_content()
        mocker.patch("plane.ext.views.import_job.upload_import_source", return_value=True)
        enqueue = mocker.patch("plane.ext.views.import_job.run_todoist_import.apply_async")

        response = client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": parse_todoist_csv(content).digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        enqueue.assert_called_once()

    def test_cancel_requires_valid_csrf_token(self, mocker, workspace, import_project, create_user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(create_user)
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="e" * 64,
            source_key="imports/source.csv",
            status=ImportJob.Status.QUEUED,
        )

        rejected = client.post(f"/api/workspaces/{workspace.slug}/imports/{job.id}/cancel/")

        assert rejected.status_code == status.HTTP_403_FORBIDDEN
        job.refresh_from_db()
        assert job.status == ImportJob.Status.QUEUED

        csrf_response = client.get("/auth/get-csrf-token/")
        mocker.patch("plane.ext.views.import_job.delete_import_source", return_value=True)
        accepted = client.post(
            f"/api/workspaces/{workspace.slug}/imports/{job.id}/cancel/",
            HTTP_X_CSRFTOKEN=csrf_response.data["csrf_token"],
        )

        assert accepted.status_code == status.HTTP_200_OK
        job.refresh_from_db()
        assert job.status == ImportJob.Status.CANCELLED

    def test_admin_can_preview_without_persisting_source(self, session_client, workspace, import_project):
        response = session_client.post(
            preview_url(workspace),
            {"project_id": str(import_project.id), "file": upload()},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["counts"]["task"] == 1
        assert response.data["assignees"] == ("Owner (100)",)
        assert response.data["duplicate"] is False
        assert ImportJob.objects.count() == 0

    def test_workspace_member_cannot_preview(self, workspace, import_project):
        email = f"member-{uuid4().hex[:8]}@hangar.test"
        user = User.objects.create(email=email, username=email)
        WorkspaceMember.objects.create(workspace=workspace, member=user, role=15, is_active=True)
        ProjectMember.objects.create(project=import_project, member=user, role=15, is_active=True)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.post(
            preview_url(workspace),
            {"project_id": str(import_project.id), "file": upload()},
            format="multipart",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cross_workspace_project_is_rejected(self, session_client, workspace, create_user):
        other_workspace = Workspace.objects.create(
            name="Other",
            slug=f"other-{uuid4().hex[:8]}",
            owner=create_user,
        )
        other_project = Project.objects.create(
            name="Other project",
            identifier="OTH",
            workspace=other_workspace,
        )

        response = session_client.post(
            preview_url(workspace),
            {"project_id": str(other_project.id), "file": upload()},
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "invalid_project"

    def test_start_queues_private_import(self, mocker, session_client, workspace, import_project):
        content = csv_content()
        digest = parse_todoist_csv(content).digest
        upload_source = mocker.patch("plane.ext.views.import_job.upload_import_source", return_value=True)
        enqueue = mocker.patch("plane.ext.views.import_job.run_todoist_import.apply_async")

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        job = ImportJob.objects.get()
        assert job.status == ImportJob.Status.QUEUED
        assert job.source_key.startswith(f"imports/{workspace.id}/{job.id}/")
        upload_source.assert_called_once()
        enqueue.assert_called_once_with(args=[str(job.id)], task_id=job.celery_task_id)

    def test_invalid_assignee_mapping_is_rejected(self, session_client, workspace, import_project):
        content = csv_content()
        digest = parse_todoist_csv(content).digest
        email = f"outsider-{uuid4().hex[:8]}@hangar.test"
        outsider = User.objects.create(email=email, username=email)

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": digest,
                "config": json.dumps(
                    {
                        "assignee_mapping": {"Owner (100)": str(outsider.id)},
                        "module_conflicts": {},
                    }
                ),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "invalid_assignee_mapping"
        assert ImportJob.objects.count() == 0

    def test_rows_with_errors_require_explicit_skip_confirmation(self, session_client, workspace, import_project):
        content = csv_content().replace(b",4,1,", b",9,1,", 1)
        preview = parse_todoist_csv(content)
        assert preview.errors

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": preview.digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "skipped_rows_not_confirmed"
        assert ImportJob.objects.count() == 0

    def test_upload_failure_keeps_source_key_for_cleanup(self, mocker, session_client, workspace, import_project):
        content = csv_content()
        digest = parse_todoist_csv(content).digest
        mocker.patch("plane.ext.views.import_job.upload_import_source", return_value=False)
        enqueue = mocker.patch("plane.ext.views.import_job.run_todoist_import.apply_async")

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        job = ImportJob.objects.get()
        assert job.status == ImportJob.Status.FAILED
        assert job.source_key
        enqueue.assert_not_called()

    def test_queue_failure_keeps_source_key_when_immediate_cleanup_fails(
        self, mocker, session_client, workspace, import_project
    ):
        content = csv_content()
        digest = parse_todoist_csv(content).digest
        mocker.patch("plane.ext.views.import_job.upload_import_source", return_value=True)
        mocker.patch("plane.ext.views.import_job.delete_import_source", return_value=False)
        mocker.patch(
            "plane.ext.views.import_job.run_todoist_import.apply_async",
            side_effect=RuntimeError("broker unavailable"),
        )

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        job = ImportJob.objects.get()
        assert job.status == ImportJob.Status.FAILED
        assert job.source_key
        assert job.config == {}

    def test_exact_duplicate_requires_confirmation(self, session_client, workspace, import_project, create_user):
        content = csv_content()
        digest = parse_todoist_csv(content).digest
        ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest=digest,
            status=ImportJob.Status.COMPLETED,
        )

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "duplicate_import"

    def test_report_is_scoped_and_excludes_private_job_configuration(
        self, session_client, workspace, import_project, create_user
    ):
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="a" * 64,
            config={"private-source-identity": "private-member"},
            stats={"imported_tasks": 1},
            errors=[],
            status=ImportJob.Status.COMPLETED,
        )

        response = session_client.get(f"/api/workspaces/{workspace.slug}/imports/{job.id}/report/")

        assert response.status_code == status.HTTP_200_OK
        assert response["Cache-Control"] == "no-store"
        assert response["X-Content-Type-Options"] == "nosniff"
        body = response.content.decode()
        assert "imported_tasks" in body
        assert "private-source-identity" not in body
        assert "private-member" not in body

    def test_processing_cancel_requests_worker_shutdown_without_deleting_source(
        self, mocker, session_client, workspace, import_project, create_user
    ):
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="b" * 64,
            source_key="imports/source.csv",
            status=ImportJob.Status.PROCESSING,
        )
        delete_source = mocker.patch("plane.ext.views.import_job.delete_import_source")

        response = session_client.post(f"/api/workspaces/{workspace.slug}/imports/{job.id}/cancel/")

        assert response.status_code == status.HTTP_202_ACCEPTED
        job.refresh_from_db()
        assert job.cancel_requested_at is not None
        delete_source.assert_not_called()

    def test_unknown_configuration_option_is_rejected(self, session_client, workspace, import_project):
        content = csv_content()
        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": parse_todoist_csv(content).digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}, "unexpected": True}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "invalid_config"

    def test_nested_module_conflict_configuration_is_strict(self, session_client, workspace, import_project):
        module = Module.objects.create(name="Existing", project=import_project)
        content = section_csv(module.name)
        preview = parse_todoist_csv(content)
        conflict = preview.records[0]

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": preview.digest,
                "config": json.dumps(
                    {
                        "assignee_mapping": {},
                        "module_conflicts": {
                            str(conflict.row): {
                                "action": "reuse",
                                "module_id": str(module.id),
                                "unexpected": True,
                            }
                        },
                    }
                ),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"]["code"] == "invalid_module_conflict"

    def test_failed_import_retry_reuses_job_identity(
        self, mocker, session_client, workspace, import_project, create_user
    ):
        content = csv_content()
        digest = parse_todoist_csv(content).digest
        failed_job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest=digest,
            status=ImportJob.Status.FAILED,
        )
        mocker.patch("plane.ext.views.import_job.upload_import_source", return_value=True)
        enqueue = mocker.patch("plane.ext.views.import_job.run_todoist_import.apply_async")

        response = session_client.post(
            import_url(workspace),
            {
                "project_id": str(import_project.id),
                "preview_digest": digest,
                "config": json.dumps({"assignee_mapping": {}, "module_conflicts": {}}),
                "file": upload(content),
            },
            format="multipart",
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert ImportJob.objects.count() == 1
        failed_job.refresh_from_db()
        assert failed_job.status == ImportJob.Status.QUEUED
        enqueue.assert_called_once_with(args=[str(failed_job.id)], task_id=failed_job.celery_task_id)

    def test_report_is_not_available_while_processing(self, session_client, workspace, import_project, create_user):
        job = ImportJob.objects.create(
            workspace=workspace,
            project=import_project,
            initiated_by=create_user,
            source_digest="c" * 64,
            status=ImportJob.Status.PROCESSING,
        )

        response = session_client.get(f"/api/workspaces/{workspace.slug}/imports/{job.id}/report/")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["error"]["code"] == "report_not_ready"
