# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import UUID

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.db.models import Issue, IssueType, Workspace, WorkspaceMember
from plane.ext.models import (
    CapacityAuditEvent,
    WorkshopChecklistItem,
    WorkshopChecklistTemplate,
)
from plane.ext.models.workshop_template import (
    MAX_ITEMS_PER_TEMPLATE,
    MAX_OFFSET_DAYS,
    MAX_TEMPLATES_PER_WORKSPACE,
)
from plane.ext.services.workshop_checklist import apply_checklist_template
from plane.ext.views.capacity import _audit, _disabled
from plane.utils.permissions import ROLE, allow_permission

ASSIGNEE_MODES = {choice for choice, _ in WorkshopChecklistItem.AssigneeMode.choices}


def _item_payload(item):
    return {
        "id": str(item.id),
        "position": item.position,
        "title": item.title,
        "description": item.description,
        "assignee_id": str(item.assignee_id) if item.assignee_id else None,
        "assignee_mode": item.assignee_mode,
        "offset_days": item.offset_days,
    }


def _template_payload(template):
    return {
        "id": str(template.id),
        "name": template.name,
        "is_default": template.is_default,
        "items": [_item_payload(item) for item in template.items.all()],
    }


def _parse_items(raw, *, workspace):
    """Validate the whole list before touching anything.

    Returns `(items, error_response)`. Partially applying an edit would leave a
    template in a shape its author never asked for, so nothing is written until
    every row is known to be good.
    """
    if not isinstance(raw, list):
        return None, Response({"error": "Send `items` as a list."}, status=400)
    if len(raw) > MAX_ITEMS_PER_TEMPLATE:
        return None, Response({"error": f"Use at most {MAX_ITEMS_PER_TEMPLATE} checklist items."}, status=400)

    cleaned = []
    seen_titles = set()
    for position, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return None, Response({"error": f"Item {position + 1} must be an object."}, status=400)
        title = entry.get("title")
        if not isinstance(title, str) or not title.strip() or len(title) > 255:
            return None, Response({"error": f"Item {position + 1} requires a title of up to 255 characters."}, status=400)
        title = title.strip()
        # The checklist is applied by name, so two items sharing one would make
        # the second permanently unappliable.
        if title.casefold() in seen_titles:
            return None, Response({"error": f"Item {position + 1} repeats the title {title!r}."}, status=400)
        seen_titles.add(title.casefold())

        description = entry.get("description", "")
        if not isinstance(description, str) or len(description) > 5000:
            return None, Response({"error": f"Item {position + 1}: description must be text under 5000 characters."}, status=400)

        mode = entry.get("assignee_mode", WorkshopChecklistItem.AssigneeMode.UNASSIGNED)
        if mode not in ASSIGNEE_MODES:
            return None, Response({"error": f"Item {position + 1}: unknown assignee mode {mode!r}."}, status=400)

        assignee_id = entry.get("assignee_id")
        if mode == WorkshopChecklistItem.AssigneeMode.FIXED:
            try:
                assignee_id = UUID(str(assignee_id))
            except (TypeError, ValueError):
                return None, Response({"error": f"Item {position + 1} requires a valid assignee."}, status=400)
            if not WorkspaceMember.objects.filter(
                workspace=workspace, member_id=assignee_id, is_active=True
            ).exists():
                return None, Response(
                    {"error": f"Item {position + 1}: that person is not an active member of this workspace."},
                    status=400,
                )
        else:
            assignee_id = None

        try:
            offset_days = int(entry.get("offset_days", 0))
        except (TypeError, ValueError):
            return None, Response({"error": f"Item {position + 1}: offset_days must be a whole number."}, status=400)
        if not -MAX_OFFSET_DAYS <= offset_days <= MAX_OFFSET_DAYS:
            return None, Response(
                {"error": f"Item {position + 1}: offset_days must be between -{MAX_OFFSET_DAYS} and {MAX_OFFSET_DAYS}."},
                status=400,
            )

        cleaned.append(
            {
                "position": position,
                "title": title,
                "description": description,
                "assignee_id": assignee_id,
                "assignee_mode": mode,
                "offset_days": offset_days,
            }
        )
    return cleaned, None


def _write_items(template, items, actor):
    # Hard deletion, not the default soft one: `(template, position)` is unique
    # without a `deleted_at IS NULL` condition, so a soft-deleted row would keep
    # its position reserved and the very next save would collide with a ghost.
    template.items.all().delete(soft=False)
    WorkshopChecklistItem.objects.bulk_create(
        [
            WorkshopChecklistItem(
                template=template,
                created_by=actor,
                updated_by=actor,
                **values,
            )
            for values in items
        ]
    )


class WorkshopChecklistTemplateListEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        templates = (
            WorkshopChecklistTemplate.objects.filter(workspace__slug=slug)
            .prefetch_related("items")
            .order_by("name", "id")
        )
        return Response({"results": [_template_payload(template) for template in templates]})

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    @transaction.atomic
    def post(self, request, slug):
        if response := _disabled():
            return response
        workspace = get_object_or_404(Workspace.objects.select_for_update(), slug=slug)
        name = request.data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            return Response({"error": "A template needs a name of up to 120 characters."}, status=400)
        name = name.strip()
        if WorkshopChecklistTemplate.objects.filter(workspace=workspace).count() >= MAX_TEMPLATES_PER_WORKSPACE:
            return Response({"error": f"Use at most {MAX_TEMPLATES_PER_WORKSPACE} templates."}, status=400)
        if WorkshopChecklistTemplate.objects.filter(workspace=workspace, name=name).exists():
            return Response({"error": "A template with that name already exists."}, status=400)

        items, error = _parse_items(request.data.get("items", []), workspace=workspace)
        if error:
            return error

        is_default = bool(request.data.get("is_default"))
        template = WorkshopChecklistTemplate.objects.create(
            workspace=workspace,
            name=name,
            is_default=is_default,
            created_by=request.user,
            updated_by=request.user,
        )
        if is_default:
            WorkshopChecklistTemplate.objects.filter(workspace=workspace, is_default=True).exclude(
                pk=template.pk
            ).update(is_default=False)
        _write_items(template, items, request.user)
        _audit(
            request,
            workspace_id=workspace.id,
            action=CapacityAuditEvent.Action.CHECKLIST_TEMPLATE_UPDATED,
            metadata={"template_id": str(template.id), "item_count": len(items)},
        )
        return Response(_template_payload(template), status=201)


class WorkshopChecklistTemplateDetailEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    @transaction.atomic
    def put(self, request, slug, template_id):
        if response := _disabled():
            return response
        template = get_object_or_404(
            WorkshopChecklistTemplate.objects.select_for_update().select_related("workspace"),
            workspace__slug=slug,
            pk=template_id,
        )
        name = request.data.get("name", template.name)
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            return Response({"error": "A template needs a name of up to 120 characters."}, status=400)
        name = name.strip()
        if (
            WorkshopChecklistTemplate.objects.filter(workspace=template.workspace, name=name)
            .exclude(pk=template.pk)
            .exists()
        ):
            return Response({"error": "A template with that name already exists."}, status=400)

        items, error = _parse_items(request.data.get("items", []), workspace=template.workspace)
        if error:
            return error

        template.name = name
        template.is_default = bool(request.data.get("is_default", template.is_default))
        template.updated_by = request.user
        template.save(update_fields=["name", "is_default", "updated_by", "updated_at"])
        if template.is_default:
            WorkshopChecklistTemplate.objects.filter(workspace=template.workspace, is_default=True).exclude(
                pk=template.pk
            ).update(is_default=False)
        _write_items(template, items, request.user)
        _audit(
            request,
            workspace_id=template.workspace_id,
            action=CapacityAuditEvent.Action.CHECKLIST_TEMPLATE_UPDATED,
            metadata={"template_id": str(template.id), "item_count": len(items)},
        )
        return Response(_template_payload(template))

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, template_id):
        if response := _disabled():
            return response
        template = get_object_or_404(WorkshopChecklistTemplate, workspace__slug=slug, pk=template_id)
        workspace_id = template.workspace_id
        template.delete()
        _audit(
            request,
            workspace_id=workspace_id,
            action=CapacityAuditEvent.Action.CHECKLIST_TEMPLATE_REMOVED,
            metadata={"template_id": str(template_id)},
        )
        return Response(status=204)


class WorkshopApplyChecklistEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id, issue_id):
        if response := _disabled():
            return response
        issue = get_object_or_404(
            Issue.objects.select_related("type"), workspace__slug=slug, project_id=project_id, pk=issue_id
        )
        if not issue.type_id or issue.type.system_key != IssueType.SystemKey.WORKSHOP:
            return Response({"error": "Only Workshop work items take a checklist."}, status=400)

        template_id = request.data.get("template_id")
        if template_id:
            template = get_object_or_404(
                WorkshopChecklistTemplate.objects.prefetch_related("items"),
                workspace_id=issue.workspace_id,
                pk=template_id,
            )
        else:
            template = (
                WorkshopChecklistTemplate.objects.filter(workspace_id=issue.workspace_id, is_default=True)
                .prefetch_related("items")
                .first()
            )
            if template is None:
                return Response({"error": "This workspace has no default checklist template."}, status=404)

        result = apply_checklist_template(
            template=template, issue=issue, actor=request.user, request=request
        )
        _audit(
            request,
            workspace_id=issue.workspace_id,
            issue_id=issue.id,
            action=CapacityAuditEvent.Action.CHECKLIST_APPLIED,
            metadata={"template_id": str(template.id), "created_count": len(result["created"])},
        )
        return Response(
            {
                "created": [
                    {"id": str(child.id), "name": child.name, "target_date": child.target_date}
                    for child in result["created"]
                ],
                "skipped_assignees": result["skipped_assignees"],
            },
            status=201,
        )
