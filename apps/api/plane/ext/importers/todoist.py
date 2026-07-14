# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from html import escape
from typing import Any

# Django imports
from django.db import transaction

# Third party imports
from crum import impersonate

# Module imports
from plane.app.serializers.issue import IssueCommentSerializer, IssueCreateSerializer
from plane.app.serializers.project import ProjectSerializer
from plane.db.models import Issue, IssueActivity, IssueComment, Module, ModuleIssue
from plane.utils.content_validator import validate_html_content
from plane.utils.markdown import markdown

from plane.ext.models import ImportJob
from plane.ext.utils.import_storage import read_import_source
from plane.ext.utils.importers.todoist_csv import TodoistRecord, parse_todoist_csv


EXTERNAL_SOURCE = "todoist_csv"


class ImportRowFailure(Exception):
    def __init__(self, code: str, field: str | None = None):
        super().__init__(code)
        self.code = code
        self.field = field


def _diagnostic(row: int | None, code: str, field: str | None = None) -> dict[str, Any]:
    return {
        "level": "error",
        "code": code,
        "message": "This row could not be imported.",
        "row": row,
        "field": field,
    }


def _render_markdown(value: str) -> str:
    rendered = markdown(value or "") or "<p></p>"
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
    if not values:
        return None
    items = "".join(f"<li>{value}</li>" for value in values)
    return f"<p><strong>Imported scheduling details</strong></p><ul>{items}</ul>"


def _create_activity(issue: Issue, actor_id, *, comment: IssueComment | None = None) -> None:
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


def _create_comment(job: ImportJob, issue: Issue, record: TodoistRecord, comment_html: str) -> IssueComment:
    external_id = f"{job.id}:{record.row}"
    existing = IssueComment.objects.filter(
        issue=issue,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    ).first()
    if existing:
        return existing

    serializer = IssueCommentSerializer(
        data={
            "comment_html": comment_html,
            "external_source": EXTERNAL_SOURCE,
            "external_id": external_id,
        }
    )
    if not serializer.is_valid():
        raise ImportRowFailure("invalid_comment", "content")
    comment = serializer.save(
        project_id=job.project_id,
        issue_id=issue.id,
        actor=job.initiated_by,
    )
    _create_activity(issue, job.initiated_by_id, comment=comment)
    return comment


def _create_module(job: ImportJob, record: TodoistRecord) -> Module:
    external_id = f"{job.id}:{record.row}"
    existing = Module.objects.filter(
        project=job.project,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    ).first()
    if existing:
        return existing

    conflict = job.config.get("module_conflicts", {}).get(str(record.row), {})
    action = conflict.get("action")
    if action == "reuse":
        module = Module.objects.filter(
            id=conflict.get("module_id"),
            project=job.project,
        ).first()
        if not module:
            raise ImportRowFailure("module_conflict_target_missing", "content")
        return module

    name = conflict.get("name") if action == "rename" else record.content
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
        raise ImportRowFailure("invalid_module_name", "content")
    if Module.objects.filter(project=job.project, name=name.strip()).exists():
        raise ImportRowFailure("module_name_conflict", "content")

    return Module.objects.create(
        name=name.strip(),
        project=job.project,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    )


def _create_issue(
    job: ImportJob,
    record: TodoistRecord,
    parent: Issue | None,
) -> Issue:
    external_id = f"{job.id}:{record.row}"
    existing = Issue.objects.filter(
        project=job.project,
        external_source=EXTERNAL_SOURCE,
        external_id=external_id,
    ).first()
    if existing:
        return existing

    start_date = record.scheduled_date if record.deadline else None
    target_date = record.deadline or record.scheduled_date
    assignee_id = job.config.get("assignee_mapping", {}).get(record.responsible)
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
    issue = serializer.save()
    _create_activity(issue, job.initiated_by_id)
    return issue


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


def execute_todoist_import(job: ImportJob) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
        "skipped": preview.counts.get("blank", 0) + preview.counts.get("meta", 0),
        "failed": preview.counts.get("failed", 0),
        "processed_tasks": 0,
    }
    issues_by_row: dict[int, Issue] = {}
    modules_by_row: dict[int, Module] = {}

    if any(record.kind == "section" for record in preview.records) and not job.project.module_view:
        job.project.module_view = True
        job.project.save(update_fields=["module_view"])

    with impersonate(job.initiated_by):
        for record in preview.records:
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
                                        "The project note was skipped because the project already has a description."
                                    ),
                                    "row": record.row,
                                    "field": "content",
                                }
                            )
                        continue

                    if record.kind == "section":
                        modules_by_row[record.row] = _create_module(job, record)
                        stats["imported_sections"] += 1
                        continue

                    if record.kind == "note":
                        issue = issues_by_row.get(record.task_row or -1)
                        if not issue:
                            raise ImportRowFailure("note_dependency_failed", "type")
                        _create_comment(job, issue, record, _render_markdown(record.content))
                        stats["imported_notes"] += 1
                        continue

                    parent = None
                    if record.parent_row is not None:
                        parent = issues_by_row.get(record.parent_row)
                        if parent is None:
                            raise ImportRowFailure("parent_dependency_failed", "indent")
                    issue = _create_issue(job, record, parent)
                    if record.section_row is not None:
                        module = modules_by_row.get(record.section_row)
                        if module is None:
                            raise ImportRowFailure("module_dependency_failed", "type")
                        ModuleIssue.objects.get_or_create(module=module, issue=issue, project=job.project)
                    metadata = _metadata_comment(record)
                    if metadata:
                        _create_comment(job, issue, record, metadata)
                    issues_by_row[record.row] = issue
                    stats["imported_tasks"] += 1
                    stats["processed_tasks"] += 1
            except ImportRowFailure as exc:
                diagnostics.append(_diagnostic(record.row, exc.code, exc.field))
                stats["failed"] += 1
                if record.kind == "task":
                    stats["processed_tasks"] += 1
            except Exception as exc:  # noqa: BLE001 - convert row failures to a safe report
                diagnostics.append(_diagnostic(record.row, "row_import_failed"))
                stats["failed"] += 1
                if record.kind == "task":
                    stats["processed_tasks"] += 1
                # Do not include exception messages because serializers and
                # database errors can echo private source values.
                del exc

            if stats["processed_tasks"] and stats["processed_tasks"] % 25 == 0:
                ImportJob.objects.filter(pk=job.id).update(stats=stats, errors=diagnostics)

    return stats, diagnostics
