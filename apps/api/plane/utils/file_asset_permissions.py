# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from plane.app.permissions import ROLE, issue_hidden_from_user
from plane.db.models import FileAsset, Issue, IssueComment, ProjectMember, ProjectPage, WorkspaceMember


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


def can_manage_project_cover(*, user_id, workspace_id, project_id) -> bool:
    """Authorize project-cover changes with the rule project settings use.

    The cover is part of the project's settings, which only a project admin or a
    workspace admin may change (ProjectViewSet.partial_update). Associating a
    cover asset writes project.cover_image_asset directly, so it must not be the
    side door through which a project member changes it.
    """

    return (
        is_workspace_asset_admin(
            user_id=user_id,
            workspace_id=workspace_id,
        )
        or _active_project_membership(
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        .filter(role=ROLE.ADMIN.value)
        .exists()
    )


def _asset_issue_id(asset: FileAsset):
    """The work item an asset belongs to: directly (attachments, description
    images) or through the comment it is embedded in (comment images)."""

    if asset.issue_id:
        return asset.issue_id
    if asset.comment_id:
        # all_objects: a soft-deleted comment still belongs to its work item.
        return IssueComment.all_objects.filter(pk=asset.comment_id).values_list("issue_id", flat=True).first()
    return None


def visible_work_item_fields(*, user_id, workspace, project_id, issue_id):
    """Fields that anchor a new asset to a work item the caller can see, or None.

    The work item must belong to this workspace and project and must not be hidden
    from the caller: a restricted guest only reaches work items they created, the
    rule ``issue_hidden_from_guest`` applies to the work item sub-resources and the
    dedicated attachment endpoint. A hidden work item gets the same None as a
    missing one, so the response says nothing about whether it exists.
    """
    issue = Issue.objects.filter(id=issue_id, workspace=workspace, project_id=project_id).first()
    if issue is None:
        return None
    if issue_hidden_from_user(
        user_id=user_id,
        project_id=project_id,
        issue_id=issue.id,
        workspace_scope={"workspace_id": workspace.id},
    ):
        return None
    return {"issue_id": issue.id}


def can_edit_comment(*, user_id, workspace_id, comment):
    """The rule comment editing applies (IssueCommentViewSet.partial_update through
    allow_permission): an active member of the comment's project who created it, is
    a project administrator, or is a workspace administrator."""
    membership = ProjectMember.objects.filter(
        workspace_id=workspace_id,
        project_id=comment.project_id,
        member_id=user_id,
        is_active=True,
    )
    if not membership.exists():
        return False
    if comment.created_by_id == user_id or membership.filter(role=ROLE.ADMIN.value).exists():
        return True
    return is_workspace_asset_admin(user_id=user_id, workspace_id=workspace_id)


def editable_comment_fields(*, user_id, workspace, comment):
    """Fields for an image added to a saved comment, or None.

    Binding at upload or duplication time follows the rule the bulk association
    applies: the caller may edit the comment, and its work item is not hidden from
    them.
    """
    if not can_edit_comment(user_id=user_id, workspace_id=workspace.id, comment=comment):
        return None
    if issue_hidden_from_user(
        user_id=user_id,
        project_id=comment.project_id,
        issue_id=comment.issue_id,
        workspace_scope={"workspace_id": workspace.id},
    ):
        return None
    return {"comment_id": comment.id}


def can_read_file_asset(*, user_id, asset: FileAsset) -> bool:
    """Authorize private asset reads without treating project_id=NULL as public.

    A restricted guest (a GUEST of a project with ``guest_view_all_features``
    off) only reads the assets of work items they created, together with those
    work items' comments, the rule ``issue_hidden_from_guest`` applies to the
    work item sub-resource endpoints. Every by-id read, check, duplicate and
    copy path goes through this function.
    """

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

        issue_id = _asset_issue_id(asset)
        if issue_id and issue_hidden_from_user(
            user_id=user_id,
            project_id=asset.project_id,
            issue_id=issue_id,
            workspace_scope={"workspace_id": asset.workspace_id},
        ):
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
    if asset.entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
        return bool(asset.project_id) and can_manage_project_cover(
            user_id=user_id,
            workspace_id=asset.workspace_id,
            project_id=asset.project_id,
        )
    if asset.project_id:
        project_membership = _active_project_membership(
            user_id=user_id,
            workspace_id=asset.workspace_id,
            project_id=asset.project_id,
        )
        # Active membership of the asset's project first, for a workspace admin
        # too: can_read_file_asset already refuses a non-member, and an asset a
        # caller may not read is not one they may delete, restore or rebind.
        if not project_membership.exists():
            return False
        # The work item's visibility as well, as for reads and anchoring: a
        # restricted guest changes no asset of a work item hidden from them.
        issue_id = _asset_issue_id(asset)
        if issue_id and issue_hidden_from_user(
            user_id=user_id,
            project_id=asset.project_id,
            issue_id=issue_id,
            workspace_scope={"workspace_id": asset.workspace_id},
        ):
            return False
        return (
            asset.created_by_id == user_id
            or workspace_admin
            or project_membership.filter(role=ROLE.ADMIN.value).exists()
        )
    return asset.created_by_id == user_id or workspace_admin
