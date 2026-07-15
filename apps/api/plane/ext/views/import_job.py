# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from functools import wraps
import json
from typing import Any
from uuid import UUID

# Django imports
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.db.models import Module, Project, ProjectMember, Workspace

from plane.ext.imports import ImportRetryMismatch, ImportTransitionError, todoist_imports_enabled
from plane.ext.imports.dispatcher import publish_import_dispatch
from plane.ext.imports.services import (
    fail_preparing_job,
    mark_source_deleted,
    mark_source_stored,
    request_cancellation,
    reserve_job,
)
from plane.ext.models import ImportJob
from plane.ext.serializers import ImportJobSerializer
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
ACTIVE_STATUSES = [
    ImportJob.Status.PREPARING,
    ImportJob.Status.QUEUED,
    ImportJob.Status.PROCESSING,
    ImportJob.Status.CANCELLING,
]
COMPLETED_STATUSES = [ImportJob.Status.COMPLETED, ImportJob.Status.COMPLETED_WITH_ERRORS]
TERMINAL_STATUSES = [*COMPLETED_STATUSES, ImportJob.Status.FAILED, ImportJob.Status.CANCELLED]
ALLOWED_CONFIG_KEYS = {
    "allow_duplicate",
    "allow_skipped_rows",
    "assignee_mapping",
    "module_conflicts",
}


def _error(code: str, message: str, response_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=response_status)


def todoist_imports_enabled_endpoint(view_method):
    """Fail closed before request payload validation when imports are disabled."""

    @wraps(view_method)
    def wrapped(instance, request, *args, **kwargs):
        if not todoist_imports_enabled():
            return _error(
                "importer_disabled",
                "The Todoist importer is not enabled on this instance.",
                status.HTTP_404_NOT_FOUND,
            )
        return view_method(instance, request, *args, **kwargs)

    return wrapped


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
        return (
            None,
            None,
            Response(
                {"error": exc.diagnostic.as_dict()},
                status=status.HTTP_400_BAD_REQUEST,
            ),
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
        for module in Module.objects.filter(
            project=project,
            name__in=[record.content for record in sections],
            archived_at__isnull=True,
        )
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
        status__in=COMPLETED_STATUSES,
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
    unknown_keys = sorted(set(config).difference(ALLOWED_CONFIG_KEYS))
    if unknown_keys:
        return None, _error("invalid_config", "The import configuration contains an unknown option.")
    for flag in ("allow_duplicate", "allow_skipped_rows"):
        if flag in config and not isinstance(config[flag], bool):
            return None, _error("invalid_config", f"The {flag} option must be a boolean.")
    return config, None


def _validate_assignee_mapping(
    preview: TodoistImportPreview,
    project: Project,
    config: dict[str, Any],
) -> Response | None:
    mapping = config.get("assignee_mapping", {})
    if not isinstance(mapping, dict):
        return _error("invalid_assignee_mapping", "The assignee mapping must be a JSON object.")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in mapping.items()):
        return _error("invalid_assignee_mapping", "Assignee mapping keys and values must be strings.")
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
            member__is_active=True,
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
    expected_rows = {str(conflict["row"]) for conflict in conflicts}
    if set(decisions) != expected_rows:
        return _error("invalid_module_conflicts", "Module conflict choices must match the preview exactly.")

    for conflict in conflicts:
        decision = decisions.get(str(conflict["row"]))
        if not isinstance(decision, dict):
            return _error("unresolved_module_conflict", "Resolve every module-name conflict before importing.")
        action = decision.get("action")
        if action == "reuse":
            if set(decision) != {"action", "module_id"}:
                return _error("invalid_module_conflict", "The reuse choice contains an unknown option.")
            if not isinstance(decision.get("module_id"), str) or decision["module_id"] != conflict["module_id"]:
                return _error("invalid_module_conflict", "The selected module does not match the conflict.")
            module = Module.objects.filter(
                pk=decision["module_id"],
                project=project,
                archived_at__isnull=True,
            ).first()
            if module is None:
                return _error("module_decision_stale", "Preview the import again before continuing.")
            decision["expected_name"] = module.name
            decision["expected_status"] = module.status
            decision["expected_archived_at"] = None
        elif action == "rename":
            if set(decision) != {"action", "name"}:
                return _error("invalid_module_conflict", "The rename choice contains an unknown option.")
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
    @todoist_imports_enabled_endpoint
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
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @todoist_imports_enabled_endpoint
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
        if preview.errors and config.get("allow_skipped_rows") is not True:
            return _error(
                "skipped_rows_not_confirmed",
                "Confirm that rows with validation errors may be skipped before importing.",
                status.HTTP_409_CONFLICT,
            )
        mapping_error = _validate_assignee_mapping(preview, project, config)
        if mapping_error:
            return mapping_error
        conflict_error = _validate_module_conflicts(preview, project, config)
        if conflict_error:
            return conflict_error

        duplicate = ImportJob.objects.filter(
            project=project,
            source_digest=preview.digest,
            status__in=COMPLETED_STATUSES,
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
        retry_of_id = None
        raw_retry_of_id = request.data.get("retry_job_id")
        if raw_retry_of_id:
            try:
                retry_of_id = UUID(str(raw_retry_of_id))
            except (TypeError, ValueError):
                return _error("invalid_retry", "The failed import selected for retry is invalid.")
        initial_stats = {
            "source_rows": preview.counts.get("rows", 0),
            "planned_tasks": preview.counts.get("task", 0),
            "planned_sections": preview.counts.get("section", 0),
            "planned_notes": preview.counts.get("note", 0),
            "imported_tasks": 0,
            "imported_sections": 0,
            "imported_notes": 0,
            "reused_tasks": 0,
            "reused_sections": 0,
            "reused_notes": 0,
            "imported_metadata_comments": 0,
            "reused_metadata_comments": 0,
            "failed": preview.counts.get("failed", 0),
            "processed_tasks": 0,
        }
        try:
            job = reserve_job(
                workspace=workspace,
                project=project,
                initiated_by=request.user,
                source_digest=preview.digest,
                source_size=len(content),
                config=config,
                stats=initial_stats,
                errors=[item.as_dict() for item in preview.diagnostics],
                request_id=request.headers.get("X-Request-ID"),
                retry_of_id=retry_of_id,
            )
        except ImportRetryMismatch:
            return _error(
                "invalid_retry",
                "The failed import no longer matches this source, destination, actor, or configuration.",
                status.HTTP_409_CONFLICT,
            )
        except IntegrityError:
            return _error(
                "import_in_progress",
                "Wait for the active project import to finish before starting another.",
                status.HTTP_409_CONFLICT,
            )

        object_name = job.source_key
        if not upload_import_source(content, object_name):
            fail_preparing_job(job_id=job.id, reason="upload_failed")
            return _error(
                "upload_failed",
                "The import source could not be stored. Try again.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            job, dispatch = mark_source_stored(job_id=job.id, source_key=object_name)
        except ImportTransitionError:
            delete_import_source(object_name)
            return _error(
                "import_state_changed",
                "The import was cancelled before it could be queued.",
                status.HTTP_409_CONFLICT,
            )

        publish_import_dispatch(dispatch.id)
        return Response(ImportJobSerializer(job).data, status=status.HTTP_202_ACCEPTED)


class ImportJobListEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        if not request.GET.get("cursor") or not request.GET.get("per_page"):
            return _error("missing_pagination", "The cursor and per_page parameters are required.")
        queryset = ImportJob.objects.filter(workspace__slug=slug).select_related("project", "initiated_by")
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
        if job.status not in TERMINAL_STATUSES:
            return _error(
                "report_not_ready",
                "The import report is available after the job finishes.",
                status.HTTP_409_CONFLICT,
            )
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
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ImportJobCancelEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @todoist_imports_enabled_endpoint
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug, job_id):
        job = get_object_or_404(ImportJob, pk=job_id, workspace__slug=slug)
        try:
            job, terminal = request_cancellation(
                job_id=job.id,
                actor_id=request.user.id,
                request_id=request.headers.get("X-Request-ID"),
            )
        except ImportTransitionError:
            return _error(
                "cannot_cancel",
                "Only an active import can be cancelled.",
                status.HTTP_409_CONFLICT,
            )
        response_status = status.HTTP_200_OK if terminal else status.HTTP_202_ACCEPTED
        if terminal and job.source_key and delete_import_source(job.source_key):
            job = mark_source_deleted(job_id=job.id)
        return Response(ImportJobSerializer(job).data, status=response_status)
