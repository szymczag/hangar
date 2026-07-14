# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import json
from typing import Any

# Django imports
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import Module, Project, ProjectMember, Workspace

from plane.ext.models import ImportJob
from plane.ext.serializers import ImportJobSerializer
from plane.ext.tasks import run_todoist_import
from plane.ext.utils.import_storage import delete_import_source, upload_import_source
from plane.ext.utils.importers.todoist_csv import (
    MAX_FILE_BYTES,
    TodoistImportParseError,
    TodoistImportPreview,
    parse_todoist_csv,
)


ALLOWED_CONTENT_TYPES = {
    "application/csv",
    "application/octet-stream",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
}
ACTIVE_STATUSES = [ImportJob.Status.QUEUED, ImportJob.Status.PROCESSING]


def _error(code: str, message: str, response_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=response_status)


def _read_upload(request) -> tuple[bytes | None, Response | None]:
    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        return None, _error("missing_file", "Choose a Todoist CSV file to continue.")
    if not uploaded_file.name.lower().endswith(".csv"):
        return None, _error("invalid_file_extension", "The import file must use the .csv extension.")
    content_type = (uploaded_file.content_type or "").split(";", 1)[0].lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        return None, _error("invalid_content_type", "The uploaded file is not recognized as CSV.")
    content = uploaded_file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        return None, _error("file_too_large", "The CSV file exceeds the 5 MiB import limit.")
    return content, None


def _parse_upload(request) -> tuple[TodoistImportPreview | None, bytes | None, Response | None]:
    content, upload_error = _read_upload(request)
    if upload_error:
        return None, None, upload_error
    try:
        return parse_todoist_csv(content or b""), content, None
    except TodoistImportParseError as exc:
        return None, None, Response(
            {"error": exc.diagnostic.as_dict()},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _project(request, slug: str) -> tuple[Project | None, Response | None]:
    project_id = request.data.get("project_id")
    if not project_id:
        return None, _error("missing_project", "Choose a destination project to continue.")
    project = Project.objects.filter(
        pk=project_id,
        workspace__slug=slug,
        archived_at__isnull=True,
    ).first()
    if project is None:
        return None, _error("invalid_project", "The destination project is not available in this workspace.")
    return project, None


def _module_conflicts(preview: TodoistImportPreview, project: Project) -> list[dict[str, str | int]]:
    sections = [record for record in preview.records if record.kind == "section"]
    modules_by_name = {
        module.name: module
        for module in Module.objects.filter(project=project, name__in=[record.content for record in sections])
    }
    return [
        {
            "row": record.row,
            "name": record.content,
            "module_id": str(modules_by_name[record.content].id),
        }
        for record in sections
        if record.content in modules_by_name
    ]


def _preview_payload(preview: TodoistImportPreview, project: Project) -> dict[str, Any]:
    duplicate = ImportJob.objects.filter(
        project=project,
        source_digest=preview.digest,
        status=ImportJob.Status.COMPLETED,
    ).exists()
    return {
        "digest": preview.digest,
        "counts": preview.counts,
        "diagnostics": [item.as_dict() for item in preview.diagnostics],
        "assignees": preview.assignees,
        "module_conflicts": _module_conflicts(preview, project),
        "project_note_action": "skip" if project.description.strip() else "set",
        "enables_modules": bool(preview.counts.get("section")) and not project.module_view,
        "duplicate": duplicate,
    }


def _load_config(request) -> tuple[dict[str, Any] | None, Response | None]:
    raw_config = request.data.get("config", "{}")
    if isinstance(raw_config, dict):
        config = raw_config
    else:
        try:
            config = json.loads(raw_config)
        except (TypeError, json.JSONDecodeError):
            return None, _error("invalid_config", "The import configuration is not valid JSON.")
    if not isinstance(config, dict):
        return None, _error("invalid_config", "The import configuration must be a JSON object.")
    return config, None


def _validate_assignee_mapping(
    preview: TodoistImportPreview,
    project: Project,
    config: dict[str, Any],
) -> Response | None:
    mapping = config.get("assignee_mapping", {})
    if not isinstance(mapping, dict):
        return _error("invalid_assignee_mapping", "The assignee mapping must be a JSON object.")
    if not set(mapping).issubset(preview.assignees):
        return _error("invalid_assignee_mapping", "The assignee mapping contains an unknown source identity.")

    member_ids = {str(value) for value in mapping.values() if value}
    valid_member_ids = {
        str(member_id)
        for member_id in ProjectMember.objects.filter(
            project=project,
            member_id__in=member_ids,
            role__gte=ROLE.MEMBER.value,
            is_active=True,
        ).values_list("member_id", flat=True)
    }
    if member_ids != valid_member_ids:
        return _error("invalid_assignee_mapping", "Every mapped assignee must be an active project member.")
    config["assignee_mapping"] = {key: str(value) for key, value in mapping.items() if value}
    return None


def _validate_module_conflicts(
    preview: TodoistImportPreview,
    project: Project,
    config: dict[str, Any],
) -> Response | None:
    conflicts = _module_conflicts(preview, project)
    decisions = config.get("module_conflicts", {})
    if not isinstance(decisions, dict):
        return _error("invalid_module_conflicts", "Module conflict choices must be a JSON object.")

    for conflict in conflicts:
        decision = decisions.get(str(conflict["row"]))
        if not isinstance(decision, dict):
            return _error("unresolved_module_conflict", "Resolve every module-name conflict before importing.")
        action = decision.get("action")
        if action == "reuse":
            if str(decision.get("module_id")) != conflict["module_id"]:
                return _error("invalid_module_conflict", "The selected module does not match the conflict.")
        elif action == "rename":
            name = decision.get("name")
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
                return _error("invalid_module_name", "The replacement module name must contain 1 to 255 characters.")
            if Module.objects.filter(project=project, name=name.strip()).exists():
                return _error("module_name_conflict", "The replacement module name is already in use.")
            decision["name"] = name.strip()
        else:
            return _error("invalid_module_conflict", "Choose whether to reuse or rename the existing module.")
    config["module_conflicts"] = decisions
    return None


class TodoistImportPreviewEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        project, project_error = _project(request, slug)
        if project_error:
            return project_error
        assert project is not None
        preview, _, parse_error = _parse_upload(request)
        if parse_error:
            return parse_error
        assert preview is not None
        return Response(_preview_payload(preview, project), status=status.HTTP_200_OK)


class TodoistImportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        project, project_error = _project(request, slug)
        if project_error:
            return project_error
        assert project is not None
        preview, content, parse_error = _parse_upload(request)
        if parse_error:
            return parse_error
        assert preview is not None
        assert content is not None

        expected_digest = request.data.get("preview_digest")
        if not expected_digest or expected_digest != preview.digest:
            return _error("preview_mismatch", "The file changed after preview. Preview it again before importing.")

        config, config_error = _load_config(request)
        if config_error:
            return config_error
        assert config is not None
        mapping_error = _validate_assignee_mapping(preview, project, config)
        if mapping_error:
            return mapping_error
        conflict_error = _validate_module_conflicts(preview, project, config)
        if conflict_error:
            return conflict_error

        duplicate = ImportJob.objects.filter(
            project=project,
            source_digest=preview.digest,
            status=ImportJob.Status.COMPLETED,
        ).exists()
        if duplicate and config.get("allow_duplicate") is not True:
            return _error(
                "duplicate_import",
                "This exact file has already been imported into the project.",
                status.HTTP_409_CONFLICT,
            )
        if ImportJob.objects.filter(project=project, status__in=ACTIVE_STATUSES).exists():
            return _error(
                "import_in_progress",
                "Wait for the active project import to finish before starting another.",
                status.HTTP_409_CONFLICT,
            )

        workspace = Workspace.objects.get(slug=slug)
        initial_stats = {
            "source_rows": preview.counts.get("rows", 0),
            "planned_tasks": preview.counts.get("task", 0),
            "planned_sections": preview.counts.get("section", 0),
            "planned_notes": preview.counts.get("note", 0),
            "imported_tasks": 0,
            "imported_sections": 0,
            "imported_notes": 0,
            "failed": preview.counts.get("failed", 0),
            "processed_tasks": 0,
        }
        try:
            with transaction.atomic():
                job = ImportJob.objects.create(
                    workspace=workspace,
                    project=project,
                    initiated_by=request.user,
                    status=ImportJob.Status.PROCESSING,
                    source_digest=preview.digest,
                    source_size=len(content or b""),
                    config=config,
                    stats=initial_stats,
                    errors=[item.as_dict() for item in preview.diagnostics],
                )
                object_name = f"imports/{workspace.id}/{job.id}/source.csv"
                ImportJob.objects.filter(pk=job.id).update(source_key=object_name)
                job.source_key = object_name
        except IntegrityError:
            return _error(
                "import_in_progress",
                "Wait for the active project import to finish before starting another.",
                status.HTTP_409_CONFLICT,
            )

        if not upload_import_source(content or b"", object_name):
            ImportJob.objects.filter(pk=job.id).update(
                status=ImportJob.Status.FAILED,
                config={},
                reason="upload_failed",
                completed_at=timezone.now(),
            )
            return _error(
                "upload_failed",
                "The import source could not be stored. Try again.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        ImportJob.objects.filter(pk=job.id, status=ImportJob.Status.PROCESSING).update(
            status=ImportJob.Status.QUEUED
        )
        try:
            run_todoist_import.delay(str(job.id))
        except Exception:  # noqa: BLE001 - return a stable error without leaking broker details
            source_deleted = delete_import_source(object_name)
            failure_updates = {
                "status": ImportJob.Status.FAILED,
                "config": {},
                "reason": "queue_failed",
                "completed_at": timezone.now(),
            }
            if source_deleted:
                failure_updates.update(source_key="", source_deleted_at=timezone.now())
            ImportJob.objects.filter(pk=job.id, status=ImportJob.Status.QUEUED).update(
                **failure_updates
            )
            return _error(
                "queue_failed",
                "The import could not be queued. Try again.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        job.refresh_from_db()
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ImportJobListEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        if not request.GET.get("cursor") or not request.GET.get("per_page"):
            return _error("missing_pagination", "The cursor and per_page parameters are required.")
        queryset = ImportJob.objects.filter(workspace__slug=slug).select_related(
            "project", "initiated_by"
        )
        return self.paginate(
            request=request,
            queryset=queryset,
            order_by="-created_at",
            on_results=lambda jobs: ImportJobSerializer(jobs, many=True).data,
        )


class ImportJobDetailEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug, job_id):
        job = get_object_or_404(
            ImportJob.objects.select_related("project", "initiated_by"),
            pk=job_id,
            workspace__slug=slug,
        )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_200_OK)


class ImportJobReportEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug, job_id):
        job = get_object_or_404(ImportJob, pk=job_id, workspace__slug=slug)
        response = JsonResponse(
            {
                "id": str(job.id),
                "provider": job.provider,
                "status": job.status,
                "project_id": str(job.project_id),
                "stats": job.stats,
                "diagnostics": job.errors,
                "reason": job.reason,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            },
            json_dumps_params={"indent": 2},
        )
        response["Content-Disposition"] = f'attachment; filename="import-{job.id}.json"'
        return response


class ImportJobCancelEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug, job_id):
        job = get_object_or_404(ImportJob, pk=job_id, workspace__slug=slug)
        cancelled = ImportJob.objects.filter(pk=job.id, status=ImportJob.Status.QUEUED).update(
            status=ImportJob.Status.CANCELLED,
            config={},
            completed_at=timezone.now(),
        )
        if not cancelled:
            return _error("cannot_cancel", "Only a queued import can be cancelled.", status.HTTP_409_CONFLICT)
        if job.source_key and delete_import_source(job.source_key):
            ImportJob.objects.filter(pk=job.id).update(source_key="", source_deleted_at=timezone.now())
        job.refresh_from_db()
        return Response(ImportJobSerializer(job).data, status=status.HTTP_200_OK)
