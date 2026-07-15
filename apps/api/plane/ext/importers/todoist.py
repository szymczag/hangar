# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any
from uuid import UUID

# Django imports
from django.db import IntegrityError, transaction

# Third party imports
from crum import impersonate
import mistune

# Module imports
from plane.app.serializers.issue import IssueCommentSerializer, IssueCreateSerializer
from plane.app.serializers.project import ProjectSerializer
from plane.db.models import Issue, IssueActivity, IssueComment, Module, ModuleIssue
from plane.utils.content_validator import validate_html_content

from plane.ext.models import ImportJob
from plane.ext.imports.services import (
    ImportAssigneeIneligible,
    guard_mutation,
    lock_eligible_assignee,
)
from plane.ext.utils.import_storage import read_import_source
from plane.ext.utils.importers.todoist_csv import TodoistRecord, parse_todoist_csv


EXTERNAL_SOURCE = "todoist_csv"
_markdown = mistune.create_markdown()


class ImportRowFailure(Exception):
    def __init__(self, code: str, field: str | None = None):
        super().__init__(code)
        self.code = code
        self.field = field


class ImportCancelled(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ModuleBinding:
    module_id: UUID
    expected_name: str
    expected_status: str


def _diagnostic(row: int | None, code: str, field: str | None = None) -> dict[str, Any]:
    return {
        "level": "error",
        "code": code,
        "message": "This row could not be imported.",
        "row": row,
        "field": field,
    }


def _render_markdown(value: str) -> str:
    rendered = _markdown(value or "") or "<p></p>"
    is_valid, _, sanitized = validate_html_content(rendered)
    if not is_valid:
        raise ImportRowFailure("invalid_html", "description")
    return sanitized or "<p></p>"


def _metadata_comment(record: TodoistRecord) -> str | None:
    values: list[str] = []
    if record.unsupported_schedule:
        values.append(f"Original schedule: {escape(record.unsupported_schedule)}")
    if record.duration:
        unit = f" {escape(record.duration_unit)}" if record.duration_unit else ""
        values.append(f"Original duration: {escape(record.duration)}{unit}")
    if record.timezone:
        values.append(f"Original timezone: {escape(record.timezone)}")
    if not values:
        return None
    items = "".join(f"<li>{value}</li>" for value in values)
    return f"<p><strong>Imported scheduling details</strong></p><ul>{items}</ul>"


def _create_activity(issue: Issue, actor_id, *, comment: IssueComment | None = None) -> None:
    """Record import activity without dispatching interactive-create notifications."""
    if comment is None:
        IssueActivity.objects.create(
            issue=issue,
            project=issue.project,
            workspace=issue.workspace,
            comment="created the issue",
            verb="created",
            actor_id=actor_id,
            epoch=int(issue.created_at.timestamp()),
        )
        return
    IssueActivity.objects.create(
        issue=issue,
        project=issue.project,
        workspace=issue.workspace,
        comment="created a comment",
        verb="created",
        actor_id=actor_id,
        field="comment",
        new_value=comment.comment_html,
        new_identifier=comment.id,
        issue_comment=comment,
        epoch=int(comment.created_at.timestamp()),
    )


def _external_id(job: ImportJob, record: TodoistRecord) -> str:
    return f"{job.idempotency_namespace}:{record.row}"


def _create_comment(
    job: ImportJob,
    issue: Issue,
    record: TodoistRecord,
    comment_html: str,
) -> tuple[IssueComment, bool]:
    external_id = _external_id(job, record)
    existing = IssueComment.objects.filter(
        issue=issue,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    ).first()
    if existing:
        return existing, False

    serializer = IssueCommentSerializer(
        data={
            "comment_html": comment_html,
            "external_source": EXTERNAL_SOURCE,
            "external_id": external_id,
        }
    )
    if not serializer.is_valid():
        raise ImportRowFailure("invalid_comment", "content")
    try:
        with transaction.atomic():
            comment = serializer.save(
                project_id=job.project_id,
                issue_id=issue.id,
                actor=job.initiated_by,
            )
            _create_activity(issue, job.initiated_by_id, comment=comment)
        return comment, True
    except IntegrityError:
        existing = IssueComment.objects.filter(
            issue=issue,
            external_source=EXTERNAL_SOURCE,
            external_id=external_id,
        ).first()
        if existing is None:
            raise
        return existing, False


def _create_module(job: ImportJob, record: TodoistRecord) -> tuple[Module, bool]:
    external_id = _external_id(job, record)
    existing = Module.objects.filter(
        project=job.project,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    ).first()
    if existing:
        return existing, False

    conflict = job.config.get("module_conflicts", {}).get(str(record.row), {})
    action = conflict.get("action")
    if action == "reuse":
        module = (
            Module.objects.select_for_update()
            .filter(
                id=conflict.get("module_id"),
                project=job.project,
            )
            .first()
        )
        if (
            module is None
            or module.name != conflict.get("expected_name")
            or module.status != conflict.get("expected_status")
            or module.archived_at is not None
            or conflict.get("expected_archived_at", "missing") is not None
        ):
            raise ImportRowFailure("module_decision_stale", "content")
        return module, False

    name = conflict.get("name") if action == "rename" else record.content
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
        raise ImportRowFailure("invalid_module_name", "content")
    if Module.objects.filter(project=job.project, name=name.strip()).exists():
        raise ImportRowFailure("module_name_conflict", "content")

    try:
        with transaction.atomic():
            module = Module.objects.create(
                name=name.strip(),
                project=job.project,
                external_source=EXTERNAL_SOURCE,
                external_id=external_id,
            )
        return module, True
    except IntegrityError:
        existing = Module.objects.filter(
            project=job.project,
            external_source=EXTERNAL_SOURCE,
            external_id=external_id,
        ).first()
        if existing is not None:
            return existing, False
        raise ImportRowFailure("module_name_conflict", "content") from None


def _module_binding(module: Module) -> ModuleBinding:
    return ModuleBinding(
        module_id=module.id,
        expected_name=module.name,
        expected_status=module.status,
    )


def _lock_bound_module(job: ImportJob, binding: ModuleBinding) -> Module:
    """Revalidate a section decision in the task-row mutation transaction."""

    module = (
        Module.objects.select_for_update()
        .filter(
            id=binding.module_id,
            project=job.project,
        )
        .first()
    )
    if (
        module is None
        or module.name != binding.expected_name
        or module.status != binding.expected_status
        or module.archived_at is not None
    ):
        raise ImportRowFailure("module_decision_stale", "content")
    return module


def _create_issue(
    job: ImportJob,
    record: TodoistRecord,
    parent: Issue | None,
) -> tuple[Issue, bool]:
    external_id = _external_id(job, record)
    existing = Issue.objects.filter(
        project=job.project,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    ).first()
    if existing:
        return existing, False

    start_date = record.scheduled_date if record.deadline else None
    target_date = record.deadline or record.scheduled_date
    assignee_id = job.config.get("assignee_mapping", {}).get(record.responsible)
    if assignee_id:
        try:
            lock_eligible_assignee(project_id=job.project_id, assignee_id=UUID(assignee_id))
        except (ImportAssigneeIneligible, TypeError, ValueError):
            raise ImportRowFailure("assignee_no_longer_eligible", "responsible") from None
    payload: dict[str, Any] = {
        "name": record.content,
        "description_html": _render_markdown(record.description),
        "priority": record.priority,
        "parent_id": str(parent.id) if parent else None,
        "start_date": start_date,
        "target_date": target_date,
        "assignee_ids": [assignee_id] if assignee_id else [],
        "external_source": EXTERNAL_SOURCE,
        "external_id": external_id,
    }
    serializer = IssueCreateSerializer(
        data=payload,
        context={
            "project_id": job.project_id,
            "workspace_id": job.workspace_id,
            # An unmapped source assignee must remain unassigned even when the
            # project has a default assignee.
            "default_assignee_id": None,
        },
    )
    if not serializer.is_valid():
        fields = sorted(serializer.errors.keys())
        raise ImportRowFailure("invalid_task", fields[0] if fields else None)
    try:
        with transaction.atomic():
            issue = serializer.save()
            _create_activity(issue, job.initiated_by_id)
        return issue, True
    except IntegrityError:
        existing = Issue.objects.filter(
            project=job.project,
            external_source=EXTERNAL_SOURCE,
            external_id=external_id,
        ).first()
        if existing is None:
            raise
        return existing, False


def _set_project_note(job: ImportJob, record: TodoistRecord) -> bool:
    project = job.project
    if project.description.strip():
        return False
    serializer = ProjectSerializer(
        project,
        data={
            "description": record.content,
            "description_html": _render_markdown(record.content),
        },
        partial=True,
        context={"workspace_id": job.workspace_id},
    )
    if not serializer.is_valid():
        raise ImportRowFailure("invalid_project_note", "content")
    serializer.save()
    return True


def execute_todoist_import(
    job: ImportJob,
    *,
    generation: int,
    lease_token: UUID,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Execute an already-claimed Todoist import job."""

    content = read_import_source(job.source_key)
    preview = parse_todoist_csv(content)
    if preview.digest != job.source_digest:
        raise ImportRowFailure("source_digest_mismatch")

    diagnostics = [item.as_dict() for item in preview.diagnostics]
    stats: dict[str, Any] = {
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
        "skipped": preview.counts.get("blank", 0) + preview.counts.get("meta", 0),
        "failed": preview.counts.get("failed", 0),
        "processed_tasks": 0,
    }
    issues_by_row: dict[int, Issue] = {}
    modules_by_row: dict[int, ModuleBinding] = {}

    enables_modules = any(record.kind == "section" for record in preview.records)

    with impersonate(job.initiated_by):
        for record in preview.records:
            with guard_mutation(
                job_id=job.id,
                generation=generation,
                lease_token=lease_token,
            ) as guarded:
                job = guarded.job
                if enables_modules and not guarded.project.module_view:
                    guarded.project.module_view = True
                    guarded.project.save(update_fields=["module_view"])
                try:
                    with transaction.atomic():
                        if record.kind == "project_note":
                            if _set_project_note(job, record):
                                stats["imported_project_notes"] = stats.get("imported_project_notes", 0) + 1
                            else:
                                stats["skipped"] += 1
                                diagnostics.append(
                                    {
                                        "level": "warning",
                                        "code": "project_note_not_overwritten",
                                        "message": (
                                            "The project note was skipped because the project already "
                                            "has a description."
                                        ),
                                        "row": record.row,
                                        "field": "content",
                                    }
                                )
                        elif record.kind == "section":
                            module, created = _create_module(job, record)
                            modules_by_row[record.row] = _module_binding(module)
                            stats["imported_sections" if created else "reused_sections"] += 1
                        elif record.kind == "note":
                            issue = issues_by_row.get(record.task_row or -1)
                            if not issue:
                                raise ImportRowFailure("note_dependency_failed", "type")
                            _, created = _create_comment(job, issue, record, _render_markdown(record.content))
                            stats["imported_notes" if created else "reused_notes"] += 1
                        else:
                            parent = None
                            if record.parent_row is not None:
                                parent = issues_by_row.get(record.parent_row)
                                if parent is None:
                                    raise ImportRowFailure("parent_dependency_failed", "indent")
                            issue, created = _create_issue(job, record, parent)
                            if record.section_row is not None:
                                module_binding = modules_by_row.get(record.section_row)
                                if module_binding is None:
                                    raise ImportRowFailure("module_dependency_failed", "type")
                                module = _lock_bound_module(job, module_binding)
                                ModuleIssue.objects.get_or_create(
                                    module=module,
                                    issue=issue,
                                    project=job.project,
                                )
                            metadata = _metadata_comment(record)
                            if metadata:
                                _, comment_created = _create_comment(job, issue, record, metadata)
                                stats[
                                    "imported_metadata_comments" if comment_created else "reused_metadata_comments"
                                ] += 1
                            issues_by_row[record.row] = issue
                            stats["imported_tasks" if created else "reused_tasks"] += 1
                            stats["processed_tasks"] += 1
                except ImportRowFailure as exc:
                    diagnostics.append(_diagnostic(record.row, exc.code, exc.field))
                    stats["failed"] += 1
                    if record.kind == "task":
                        stats["processed_tasks"] += 1
                guarded.record_progress(stats=stats, errors=diagnostics)

    return stats, diagnostics
