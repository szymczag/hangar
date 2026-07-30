# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from plane.app.permissions import ROLE
from plane.db.models import FileAsset, ProjectMember, ProjectPage, WorkspaceMember


def is_workspace_asset_admin(*, user_id, workspace_id) -> bool:
    return WorkspaceMember.objects.filter(
        workspace_id=workspace_id,
        member_id=user_id,
        role=ROLE.ADMIN.value,
        is_active=True,
    ).exists()


def _active_project_membership(*, user_id, workspace_id, project_id):
    return ProjectMember.objects.filter(
        project_id=project_id,
        workspace_id=workspace_id,
        member_id=user_id,
        is_active=True,
    )


def can_read_file_asset(*, user_id, asset: FileAsset) -> bool:
    """Authorize private asset reads without treating project_id=NULL as public."""

    if asset.user_id:
        return asset.user_id == user_id
    if not WorkspaceMember.objects.filter(
        workspace_id=asset.workspace_id,
        member_id=user_id,
        is_active=True,
    ).exists():
        return False
    if asset.entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
        return True

    project_membership = None
    if asset.project_id:
        project_membership = _active_project_membership(
            user_id=user_id,
            workspace_id=asset.workspace_id,
            project_id=asset.project_id,
        )
        if not project_membership.exists():
            return False

    if asset.page_id:
        if asset.page.owned_by_id == user_id:
            return True
        if asset.page.access != asset.page.PUBLIC_ACCESS:
            return False
        page_links = ProjectPage.objects.filter(
            page_id=asset.page_id,
            workspace_id=asset.workspace_id,
        )
        if asset.project_id:
            return page_links.filter(project_id=asset.project_id).exists()
        return ProjectMember.objects.filter(
            project_id__in=page_links.values("project_id"),
            workspace_id=asset.workspace_id,
            member_id=user_id,
            is_active=True,
        ).exists()

    if asset.draft_issue_id:
        return asset.created_by_id == user_id and project_membership is not None
    if asset.project_id:
        return True
    return asset.created_by_id == user_id or is_workspace_asset_admin(
        user_id=user_id,
        workspace_id=asset.workspace_id,
    )


def can_mutate_file_asset(*, user_id, asset: FileAsset) -> bool:
    """Authorize delete, restore, completion, and reassociation operations."""

    workspace_admin = is_workspace_asset_admin(
        user_id=user_id,
        workspace_id=asset.workspace_id,
    )
    if asset.entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
        return workspace_admin
    if asset.entity_type in {
        FileAsset.EntityTypeContext.USER_AVATAR,
        FileAsset.EntityTypeContext.USER_COVER,
    }:
        return asset.user_id == user_id
    if asset.project_id:
        project_membership = _active_project_membership(
            user_id=user_id,
            workspace_id=asset.workspace_id,
            project_id=asset.project_id,
        )
        if not project_membership.exists() and not workspace_admin:
            return False
        return (
            asset.created_by_id == user_id
            or workspace_admin
            or project_membership.filter(role=ROLE.ADMIN.value).exists()
        )
    return asset.created_by_id == user_id or workspace_admin
