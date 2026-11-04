# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.http import HttpResponseRedirect
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from plane.db.models import DeployBoard, FileAsset, IssueComment, ProjectMember
from plane.settings.storage import S3Storage
from plane.utils.file_asset_upload import (
    UPLOAD_URL_EXPIRATION_SECONDS,
    UPLOAD_VALIDATION_VERSION,
    UploadError,
    build_pending_asset_key,
    complete_asset_upload,
    upload_error_payload,
    validate_upload_metadata,
)

# Module imports
from .base import BaseAPIView


def _active_project_board(anchor):
    return DeployBoard.objects.filter(
        anchor=anchor,
        entity_name="project",
        is_disabled=False,
    ).first()


def _active_project_member(*, deploy_board, user):
    return ProjectMember.objects.filter(
        workspace_id=deploy_board.workspace_id,
        project_id=deploy_board.project_id,
        member=user,
        is_active=True,
    ).first()


def _own_board_comment(comment_id, deploy_board, user):
    """The user's own EXTERNAL comment in the board's project, or None."""
    return IssueComment.objects.filter(
        id=comment_id,
        project_id=deploy_board.project_id,
        workspace_id=deploy_board.workspace_id,
        access="EXTERNAL",
        actor=user,
    ).first()


class EntityAssetEndpoint(BaseAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get(self, request, anchor, pk):
        # Get the deploy board
        deploy_board = _active_project_board(anchor)
        # Check if the project is published
        if not deploy_board:
            return Response(
                {"error": "Requested resource could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # get the asset id — scope to project to prevent cross-project IDOR
        asset = FileAsset.objects.get(
            workspace_id=deploy_board.workspace_id,
            project_id=deploy_board.project_id,
            pk=pk,
            entity_type__in=[
                FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
                FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            ],
        )

        # Check if the asset is uploaded
        if not asset.is_uploaded:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the presigned URL.
        # Force attachment disposition for script-capable MIME types to prevent
        # same-origin XSS when Spaces assets are served on the application's origin.
        storage = S3Storage(request=request)
        asset_mime_type = (asset.attributes.get("type") or "").split(";")[0].strip().lower()
        can_render_inline = asset.upload_validation_version == UPLOAD_VALIDATION_VERSION and asset_mime_type in {
            "image/gif",
            "image/jpeg",
            "image/png",
            "image/webp",
        }
        disposition = "inline" if can_render_inline else "attachment"
        # Generate a presigned URL to share an S3 object
        signed_url = storage.generate_presigned_url(
            object_name=asset.asset.name,
            disposition=disposition,
            content_type=(asset_mime_type if disposition == "inline" else "application/octet-stream"),
        )
        # Redirect to the signed URL
        return HttpResponseRedirect(signed_url)

    def post(self, request, anchor):
        # Get the deploy board
        deploy_board = _active_project_board(anchor)
        # Check if the project is published
        if not deploy_board:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)
        if _active_project_member(deploy_board=deploy_board, user=request.user) is None:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)

        # Public uploads are only for comment images on boards with comments enabled
        if not deploy_board.is_comments_enabled:
            return Response(
                {"error": "Comments are not enabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entity_type = request.data.get("entity_type", "")
        # The client sends "" for a comment that does not exist yet; keep such uploads unbound
        entity_identifier = request.data.get("entity_identifier") or None

        if entity_type != FileAsset.EntityTypeContext.COMMENT_DESCRIPTION:
            return Response(
                {"error": "Invalid entity type.", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # An existing comment must be the caller's own comment on this board
        entity_fields = {}
        if entity_identifier:
            comment = _own_board_comment(entity_identifier, deploy_board, request.user)
            if comment is None:
                return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)
            entity_fields = {"comment_id": comment.id}

        try:
            metadata = validate_upload_metadata(
                raw_name=request.data.get("name"),
                raw_size=request.data.get("size"),
                claimed_mime_type=request.data.get("type"),
                entity_type=entity_type,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        asset_key = build_pending_asset_key(
            namespace=str(deploy_board.workspace_id),
            name=metadata.name,
        )

        # Create a File Asset
        asset = FileAsset.objects.create(
            attributes={
                "name": metadata.name,
                "type": metadata.mime_type,
                "size": metadata.size,
            },
            asset=asset_key,
            size=metadata.size,
            workspace=deploy_board.workspace,
            created_by=request.user,
            entity_type=entity_type,
            project_id=deploy_board.project_id,
            **entity_fields,
        )

        # Get the presigned URL
        storage = S3Storage(request=request)
        # Generate a presigned URL to share an S3 object
        presigned_url = storage.generate_presigned_post(
            object_name=asset_key,
            file_type=metadata.mime_type,
            file_size=metadata.size,
            expiration=UPLOAD_URL_EXPIRATION_SECONDS,
        )
        if presigned_url is None:
            asset.delete()
            return Response(
                {
                    "error": "File storage is temporarily unavailable.",
                    "code": "upload_storage_unavailable",
                    "status": False,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        # Return the presigned URL
        return Response(
            {
                "upload_data": presigned_url,
                "asset_id": str(asset.id),
                "asset_url": asset.asset_url,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request, anchor, pk):
        # Get the deploy board
        deploy_board = _active_project_board(anchor)
        # Check if the project is published
        if not deploy_board:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)
        if _active_project_member(deploy_board=deploy_board, user=request.user) is None:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)

        asset = FileAsset.objects.filter(
            id=pk,
            workspace=deploy_board.workspace,
            project_id=deploy_board.project_id,
            created_by=request.user,
        ).first()
        if asset is None:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            complete_asset_upload(asset_id=asset.id, storage=S3Storage(request=request))
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, anchor, pk):
        # Get the deploy board
        deploy_board = _active_project_board(anchor)
        # Check if the project is published
        if not deploy_board:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)
        if _active_project_member(deploy_board=deploy_board, user=request.user) is None:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)
        # A public-site user may only delete assets they created.
        asset = FileAsset.objects.filter(
            id=pk,
            workspace=deploy_board.workspace,
            project_id=deploy_board.project_id,
            created_by=request.user,
        ).first()
        if asset is None:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Check deleted assets
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        # Save the asset
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetRestoreEndpoint(BaseAPIView):
    """Endpoint to restore a deleted assets."""

    def post(self, request, anchor, pk):
        # Get the deploy board
        deploy_board = _active_project_board(anchor)
        # Check if the project is published
        if not deploy_board:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)
        if _active_project_member(deploy_board=deploy_board, user=request.user) is None:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)

        # A public-site user may only restore assets they created.
        asset = FileAsset.all_objects.filter(
            id=pk,
            workspace=deploy_board.workspace,
            project_id=deploy_board.project_id,
            created_by=request.user,
        ).first()
        if asset is None:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        asset.is_deleted = False
        asset.deleted_at = None
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class EntityBulkAssetEndpoint(BaseAPIView):
    """Endpoint to bulk update assets."""

    def post(self, request, anchor, entity_id):
        # Get the deploy board
        deploy_board = _active_project_board(anchor)
        # Check if the project is published
        if not deploy_board:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)
        if _active_project_member(deploy_board=deploy_board, user=request.user) is None:
            return Response({"error": "Project is not published"}, status=status.HTTP_404_NOT_FOUND)

        if not deploy_board.is_comments_enabled:
            return Response(
                {"error": "Comments are not enabled for this project"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Assets may only be bound to the caller's own comment on this board
        comment = _own_board_comment(entity_id, deploy_board, request.user)
        if comment is None:
            return Response({"error": "Comment not found"}, status=status.HTTP_404_NOT_FOUND)

        asset_ids = request.data.get("asset_ids", [])

        # Check if the asset ids are provided
        if not isinstance(asset_ids, list) or not asset_ids:
            return Response({"error": "No asset ids provided."}, status=status.HTTP_400_BAD_REQUEST)

        assets = FileAsset.objects.filter(
            id__in=asset_ids,
            workspace=deploy_board.workspace,
            project_id=deploy_board.project_id,
            entity_type=FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
            # A public-site user may only rebind assets they created.
            created_by=request.user,
        )
        if assets.count() != len(set(asset_ids)):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        assets.update(comment=comment)
        return Response(status=status.HTTP_204_NO_CONTENT)
