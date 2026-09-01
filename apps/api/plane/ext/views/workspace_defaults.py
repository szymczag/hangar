# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Workspace-level home defaults and shared quick links.

Reading is open to any member; only an administrator may change what the
workspace offers. The one exception is hiding a shared link, which is a member's
own business and is deliberately not admin-gated -- it is how someone adjusts a
list they do not own without editing it for everyone else.
"""

# Django imports
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import Workspace, WorkspaceHomePreference, WorkspaceMember
from plane.ext.models import (
    WorkspaceDefaultsAdoption,
    WorkspaceHomeDefault,
    WorkspaceSharedLink,
    WorkspaceSharedLinkHide,
)

# The keys upstream's home page actually renders. Anything else would be stored
# and then silently ignored, which looks identical to the feature being broken.
ALLOWED_KEYS = {key for key, _ in WorkspaceHomePreference.HomeWidgetKeys.choices}

# Above this, rewriting every member's rows inline would hold a request open too
# long; the operation is the same either way, so it just moves to a worker.
INLINE_MEMBER_LIMIT = 300

MAX_SHARED_LINKS = 50
TITLE_MAX_LENGTH = 255


def _workspace(slug):
    return Workspace.objects.filter(slug=slug).first()


def _defaults_payload(workspace):
    rows = WorkspaceHomeDefault.objects.filter(workspace=workspace, deleted_at__isnull=True)
    return {
        "defaults": [
            {
                "key": row.key,
                "is_enabled": row.is_enabled,
                "sort_order": row.sort_order,
                "config": row.config,
            }
            for row in rows
        ],
        "version": max((row.version for row in rows), default=0),
        "available_keys": sorted(ALLOWED_KEYS),
    }


class WorkspaceHomeDefaultsEndpoint(BaseAPIView):
    """What a new member's home page starts as."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        workspace = _workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_defaults_payload(workspace), status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug):
        workspace = _workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        entries = request.data.get("defaults")
        if not isinstance(entries, list):
            return Response(
                {"error": "Send `defaults` as a list of widgets."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cleaned = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                return Response({"error": "Each default must be an object."}, status=status.HTTP_400_BAD_REQUEST)
            key = entry.get("key")
            if key not in ALLOWED_KEYS:
                return Response(
                    {"error": f"Unknown widget: {key}.", "available_keys": sorted(ALLOWED_KEYS)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if key in seen:
                return Response({"error": f"{key} is listed twice."}, status=status.HTTP_400_BAD_REQUEST)
            seen.add(key)
            cleaned.append(
                {
                    "key": key,
                    "is_enabled": bool(entry.get("is_enabled", True)),
                    "sort_order": float(entry.get("sort_order", 65535)),
                    "config": entry.get("config") if isinstance(entry.get("config"), dict) else {},
                }
            )

        apply_to_everyone = bool(request.data.get("apply_to_everyone"))

        with transaction.atomic():
            current_version = (
                WorkspaceHomeDefault.objects.filter(workspace=workspace, deleted_at__isnull=True)
                .order_by("-version")
                .values_list("version", flat=True)
                .first()
                or 0
            )
            version = current_version + 1 if apply_to_everyone else max(current_version, 1)

            WorkspaceHomeDefault.objects.filter(workspace=workspace).exclude(
                key__in=[entry["key"] for entry in cleaned]
            ).delete()

            for entry in cleaned:
                WorkspaceHomeDefault.objects.update_or_create(
                    workspace=workspace,
                    key=entry["key"],
                    defaults={
                        "is_enabled": entry["is_enabled"],
                        "sort_order": entry["sort_order"],
                        "config": entry["config"],
                        "version": version,
                    },
                )

            rewritten = 0
            if apply_to_everyone:
                rewritten = _rewrite_every_member(workspace, cleaned, version)

        payload = _defaults_payload(workspace)
        payload["members_updated"] = rewritten
        return Response(payload, status=status.HTTP_200_OK)


def _rewrite_every_member(workspace, cleaned, version):
    """Replace the managed keys on every member's home page.

    Only the keys the defaults name are touched. A preference the defaults say
    nothing about is left exactly as the person left it -- the blast radius of
    this operation is the layout an administrator actually chose, not somebody's
    whole home page.
    """
    member_ids = list(
        WorkspaceMember.objects.filter(workspace=workspace, is_active=True).values_list("member_id", flat=True)
    )
    if len(member_ids) > INLINE_MEMBER_LIMIT:
        from plane.ext.tasks import rewrite_workspace_home_defaults

        rewrite_workspace_home_defaults.delay(str(workspace.id), version)
        return len(member_ids)

    keys = [entry["key"] for entry in cleaned]
    by_key = {entry["key"]: entry for entry in cleaned}

    for member_id in member_ids:
        existing = WorkspaceHomePreference.objects.filter(workspace=workspace, user_id=member_id, key__in=keys)
        for preference in existing:
            entry = by_key[preference.key]
            preference.is_enabled = entry["is_enabled"]
            preference.sort_order = entry["sort_order"]
            preference.config = entry["config"]
            preference.save(update_fields=["is_enabled", "sort_order", "config", "updated_at"])

        present = set(existing.values_list("key", flat=True))
        WorkspaceHomePreference.objects.bulk_create(
            [
                WorkspaceHomePreference(
                    workspace=workspace,
                    user_id=member_id,
                    key=entry["key"],
                    is_enabled=entry["is_enabled"],
                    sort_order=entry["sort_order"],
                    config=entry["config"],
                )
                for entry in cleaned
                if entry["key"] not in present
            ],
            batch_size=20,
            ignore_conflicts=True,
        )

        WorkspaceDefaultsAdoption.objects.update_or_create(
            workspace=workspace, user_id=member_id, defaults={"version": version}
        )

    return len(member_ids)


def _validated_url(raw):
    """Reject anything that is not an ordinary web address.

    Mirrors what upstream does for personal quick links -- a bare host is
    treated as http, and everything is then put through Django's URLValidator,
    which is what stops `javascript:` reaching an href.
    """
    url = (raw or "").strip()
    if not url:
        raise ValidationError("A link needs a URL.")
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    URLValidator(schemes=["http", "https"])(url)
    return url


def _link_payload(link, hidden_ids):
    return {
        "id": str(link.id),
        "title": link.title,
        "url": link.url,
        "metadata": link.metadata,
        "sort_order": link.sort_order,
        "is_hidden": link.id in hidden_ids,
    }


class WorkspaceSharedLinksEndpoint(BaseAPIView):
    """Quick links the workspace gives everyone."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug):
        workspace = _workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        links = WorkspaceSharedLink.objects.filter(workspace=workspace, deleted_at__isnull=True)
        hidden_ids = set(
            WorkspaceSharedLinkHide.objects.filter(
                workspace=workspace, user=request.user, deleted_at__isnull=True
            ).values_list("shared_link_id", flat=True)
        )
        return Response([_link_payload(link, hidden_ids) for link in links], status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        workspace = _workspace(slug)
        if workspace is None:
            return Response({"error": "Workspace not found."}, status=status.HTTP_404_NOT_FOUND)

        if WorkspaceSharedLink.objects.filter(workspace=workspace, deleted_at__isnull=True).count() >= MAX_SHARED_LINKS:
            return Response(
                {"error": f"A workspace can share at most {MAX_SHARED_LINKS} links."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            url = _validated_url(request.data.get("url"))
        except ValidationError:
            return Response({"error": "That is not a valid web address."}, status=status.HTTP_400_BAD_REQUEST)

        link = WorkspaceSharedLink.objects.create(
            workspace=workspace,
            title=(request.data.get("title") or "").strip()[:TITLE_MAX_LENGTH],
            url=url,
            metadata=request.data.get("metadata") if isinstance(request.data.get("metadata"), dict) else {},
            sort_order=float(request.data.get("sort_order", 65535)),
        )
        return Response(_link_payload(link, set()), status=status.HTTP_201_CREATED)


class WorkspaceSharedLinkDetailEndpoint(BaseAPIView):
    """Edit or retire one shared link. Both reach everybody at once."""

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def patch(self, request, slug, link_id):
        link = WorkspaceSharedLink.objects.filter(pk=link_id, workspace__slug=slug, deleted_at__isnull=True).first()
        if link is None:
            return Response({"error": "Link not found."}, status=status.HTTP_404_NOT_FOUND)

        if "url" in request.data:
            try:
                link.url = _validated_url(request.data.get("url"))
            except ValidationError:
                return Response({"error": "That is not a valid web address."}, status=status.HTTP_400_BAD_REQUEST)
        if "title" in request.data:
            link.title = (request.data.get("title") or "").strip()[:TITLE_MAX_LENGTH]
        if "sort_order" in request.data:
            link.sort_order = float(request.data.get("sort_order"))
        link.save()

        return Response(_link_payload(link, set()), status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def delete(self, request, slug, link_id):
        link = WorkspaceSharedLink.objects.filter(pk=link_id, workspace__slug=slug, deleted_at__isnull=True).first()
        if link is None:
            return Response({"error": "Link not found."}, status=status.HTTP_404_NOT_FOUND)
        link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceSharedLinkHideEndpoint(BaseAPIView):
    """A member choosing whether they see one shared link.

    Deliberately open to every role. Hiding a link from your own home page is
    not an administrative act, and gating it would make "people can still
    adjust" untrue for everyone who is not an administrator.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request, slug, link_id):
        link = WorkspaceSharedLink.objects.filter(pk=link_id, workspace__slug=slug, deleted_at__isnull=True).first()
        if link is None:
            return Response({"error": "Link not found."}, status=status.HTTP_404_NOT_FOUND)

        WorkspaceSharedLinkHide.objects.get_or_create(
            workspace_id=link.workspace_id, user=request.user, shared_link=link
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def delete(self, request, slug, link_id):
        WorkspaceSharedLinkHide.objects.filter(workspace__slug=slug, user=request.user, shared_link_id=link_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
