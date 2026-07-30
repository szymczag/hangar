# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

# Module imports
from ..base import BaseAPIView, BaseViewSet
from plane.app.permissions import ROLE, WorkspaceMemberPermission
from plane.db.models import (
    DraftIssue,
    FileAsset,
    Issue,
    IssueComment,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    Workspace,
    WorkspaceMember,
)
from plane.app.serializers import FileAssetSerializer
from plane.settings.storage import S3Storage
from plane.utils.file_asset_upload import (
    UploadError,
    save_validated_multipart_asset,
    upload_error_payload,
    validate_multipart_upload,
)
from plane.utils.file_asset_permissions import (
    can_mutate_file_asset,
    can_read_file_asset,
)


def _workspace_entity_fields(*, request, workspace, entity_type, entity_id):
    """Resolve legacy multipart entity identifiers inside the URL workspace."""

    if entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
        is_admin = WorkspaceMember.objects.filter(
            workspace=workspace,
            member=request.user,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()
        if is_admin and str(entity_id) == str(workspace.id):
            return {}
        return None
    if entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
        project = Project.objects.filter(id=entity_id, workspace=workspace).first()
        if (
            project
            and ProjectMember.objects.filter(
                project=project,
                workspace=workspace,
                member=request.user,
                is_active=True,
            ).exists()
        ):
            return {"project_id": project.id}
        return None
    if entity_type in {
        FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
    }:
        issue = Issue.objects.filter(id=entity_id, workspace=workspace).first()
        if (
            issue
            and ProjectMember.objects.filter(
                project_id=issue.project_id,
                workspace=workspace,
                member=request.user,
                is_active=True,
            ).exists()
        ):
            return {"project_id": issue.project_id, "issue_id": issue.id}
        return None
    if entity_type == FileAsset.EntityTypeContext.COMMENT_DESCRIPTION:
        comment = IssueComment.objects.filter(id=entity_id, workspace=workspace).first()
        if (
            comment
            and ProjectMember.objects.filter(
                project_id=comment.project_id,
                workspace=workspace,
                member=request.user,
                is_active=True,
            ).exists()
        ):
            return {"project_id": comment.project_id, "comment_id": comment.id}
        return None
    if entity_type == FileAsset.EntityTypeContext.PAGE_DESCRIPTION:
        page = Page.objects.filter(id=entity_id, workspace=workspace).first()
        if page is None:
            return None
        if page.owned_by_id == request.user.id:
            return {"page_id": page.id}
        linked_project_ids = ProjectPage.objects.filter(
            page=page,
            workspace=workspace,
            deleted_at__isnull=True,
        ).values("project_id")
        accessible_project = (
            ProjectMember.objects.filter(
                project_id__in=linked_project_ids,
                workspace=workspace,
                member=request.user,
                is_active=True,
            )
            .values_list("project_id", flat=True)
            .first()
        )
        if page.access == Page.PUBLIC_ACCESS and accessible_project:
            return {"page_id": page.id, "project_id": accessible_project}
        return None
    if entity_type in {
        FileAsset.EntityTypeContext.DRAFT_ISSUE_ATTACHMENT,
        FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
    }:
        draft_issue = DraftIssue.objects.filter(
            id=entity_id,
            workspace=workspace,
            created_by=request.user,
        ).first()
        if (
            draft_issue
            and ProjectMember.objects.filter(
                project_id=draft_issue.project_id,
                workspace=workspace,
                member=request.user,
                is_active=True,
            ).exists()
        ):
            return {
                "project_id": draft_issue.project_id,
                "draft_issue_id": draft_issue.id,
            }
        return None
    return None


def _unexpected_legacy_fields(request, allowed_fields):
    return set(request.data) - set(allowed_fields)


class FileAssetEndpoint(BaseAPIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [IsAuthenticated, WorkspaceMemberPermission]

    """
    A viewset for viewing and editing task instances.
    """

    def get(self, request, workspace_id, asset_key):
        asset_key = str(workspace_id) + "/" + asset_key
        file_asset = FileAsset.objects.filter(
            asset=asset_key,
            workspace_id=workspace_id,
        ).first()
        if file_asset and can_read_file_asset(user_id=request.user.id, asset=file_asset):
            # Preserve the legacy response contract, which wraps the matching
            # asset in a list even though the identifier resolves one row.
            serializer = FileAssetSerializer([file_asset], context={"request": request}, many=True)
            return Response({"data": serializer.data, "status": True}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Asset key does not exist", "status": False},
                status=status.HTTP_200_OK,
            )

    def post(self, request, slug):
        # WorkspaceMemberPermission already rejects unknown slugs before this runs.
        # Use .get() so any TOCTOU race still surfaces as a 404 via ObjectDoesNotExist.
        workspace = Workspace.objects.get(slug=slug)
        uploaded_file = request.FILES.get("asset")
        entity_type = request.data.get("entity_type")
        entity_identifier = request.data.get("entity_identifier")
        if _unexpected_legacy_fields(
            request,
            {"asset", "entity_type", "entity_identifier"},
        ):
            return Response(
                {
                    "error": "Legacy upload metadata is not accepted.",
                    "code": "unsupported_legacy_field",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if uploaded_file is None:
            return Response(
                {"error": "A file is required.", "code": "missing_file", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if entity_type not in FileAsset.EntityTypeContext.values or not entity_identifier:
            return Response(
                {
                    "error": "A valid entity context is required.",
                    "code": "invalid_entity_context",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        entity_fields = _workspace_entity_fields(
            request=request,
            workspace=workspace,
            entity_type=entity_type,
            entity_id=entity_identifier,
        )
        if entity_fields is None:
            return Response(
                {
                    "error": "The entity context could not be found.",
                    "code": "invalid_entity_context",
                    "status": False,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            metadata = validate_multipart_upload(
                uploaded_file=uploaded_file,
                entity_type=entity_type,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        try:
            asset = save_validated_multipart_asset(
                uploaded_file=uploaded_file,
                metadata=metadata,
                storage=S3Storage(request=request, is_server=True),
                namespace=workspace.id,
                created_by_id=request.user.id,
                entity_type=entity_type,
                entity_identifier=entity_identifier,
                workspace_id=workspace.id,
                **entity_fields,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        return Response(FileAssetSerializer(asset).data, status=status.HTTP_201_CREATED)

    def delete(self, request, workspace_id, asset_key):
        asset_key = str(workspace_id) + "/" + asset_key
        file_asset = FileAsset.objects.filter(
            asset=asset_key,
            workspace_id=workspace_id,
        ).first()
        if file_asset is None or not can_mutate_file_asset(
            user_id=request.user.id,
            asset=file_asset,
        ):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        file_asset.is_deleted = True
        file_asset.deleted_at = timezone.now()
        file_asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class FileAssetViewSet(BaseViewSet):
    permission_classes = [IsAuthenticated, WorkspaceMemberPermission]

    def restore(self, request, workspace_id, asset_key):
        asset_key = str(workspace_id) + "/" + asset_key
        file_asset = FileAsset.all_objects.filter(
            asset=asset_key,
            workspace_id=workspace_id,
        ).first()
        if file_asset is None or not can_mutate_file_asset(
            user_id=request.user.id,
            asset=file_asset,
        ):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        file_asset.is_deleted = False
        file_asset.deleted_at = None
        file_asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserAssetsEndpoint(BaseAPIView):
    parser_classes = (MultiPartParser, FormParser)

    def get(self, request, asset_key):
        files = FileAsset.objects.filter(asset=asset_key, created_by=request.user)
        if files.exists():
            serializer = FileAssetSerializer(files, context={"request": request})
            return Response({"data": serializer.data, "status": True}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Asset key does not exist", "status": False},
                status=status.HTTP_200_OK,
            )

    def post(self, request):
        uploaded_file = request.FILES.get("asset")
        entity_type = request.data.get("entity_type")
        if _unexpected_legacy_fields(request, {"asset", "entity_type"}):
            return Response(
                {
                    "error": "Legacy upload metadata is not accepted.",
                    "code": "unsupported_legacy_field",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if uploaded_file is None:
            return Response(
                {"error": "A file is required.", "code": "missing_file", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if entity_type not in {
            FileAsset.EntityTypeContext.USER_AVATAR,
            FileAsset.EntityTypeContext.USER_COVER,
        }:
            return Response(
                {
                    "error": "A valid user asset context is required.",
                    "code": "invalid_entity_context",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            metadata = validate_multipart_upload(
                uploaded_file=uploaded_file,
                entity_type=entity_type,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        try:
            asset = save_validated_multipart_asset(
                uploaded_file=uploaded_file,
                metadata=metadata,
                storage=S3Storage(request=request, is_server=True),
                namespace=f"user-{request.user.id}",
                created_by_id=request.user.id,
                entity_type=entity_type,
                entity_identifier=request.user.id,
                user_id=request.user.id,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        return Response(FileAssetSerializer(asset).data, status=status.HTTP_201_CREATED)

    def delete(self, request, asset_key):
        file_asset = FileAsset.objects.get(asset=asset_key, created_by=request.user)
        file_asset.is_deleted = True
        file_asset.save(update_fields=["is_deleted"])
        return Response(status=status.HTTP_204_NO_CONTENT)
