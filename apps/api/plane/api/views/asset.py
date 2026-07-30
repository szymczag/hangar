# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django Imports
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response
from drf_spectacular.utils import OpenApiExample, OpenApiRequest

# Module Imports
from plane.settings.storage import S3Storage
from plane.db.models import FileAsset, Project, ProjectMember, User, Workspace
from plane.app.permissions import WorkspaceUserPermission
from plane.api.views.base import BaseAPIView
from plane.api.serializers import (
    UserAssetUploadSerializer,
    AssetUpdateSerializer,
    GenericAssetUploadSerializer,
    GenericAssetUpdateSerializer,
)
from plane.utils.openapi import (
    ASSET_ID_PARAMETER,
    WORKSPACE_SLUG_PARAMETER,
    PRESIGNED_URL_SUCCESS_RESPONSE,
    GENERIC_ASSET_UPLOAD_SUCCESS_RESPONSE,
    GENERIC_ASSET_VALIDATION_ERROR_RESPONSE,
    ASSET_CONFLICT_RESPONSE,
    ASSET_DOWNLOAD_SUCCESS_RESPONSE,
    ASSET_DOWNLOAD_ERROR_RESPONSE,
    ASSET_UPDATED_RESPONSE,
    ASSET_DELETED_RESPONSE,
    VALIDATION_ERROR_RESPONSE,
    ASSET_NOT_FOUND_RESPONSE,
    NOT_FOUND_RESPONSE,
    UNAUTHORIZED_RESPONSE,
    asset_docs,
)
from plane.utils.exception_logger import log_exception
from plane.utils.file_asset_upload import (
    UPLOAD_URL_EXPIRATION_SECONDS,
    UPLOAD_VALIDATION_VERSION,
    RASTER_IMAGE_MIME_BY_EXTENSION,
    UploadError,
    build_pending_asset_key,
    complete_asset_upload,
    upload_error_payload,
    validate_upload_metadata,
)
from plane.utils.file_asset_permissions import can_read_file_asset


class UserAssetEndpoint(BaseAPIView):
    """This endpoint is used to upload user profile images."""

    def asset_delete(self, asset_id):
        asset = FileAsset.objects.filter(id=asset_id).first()
        if asset is None:
            return
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return

    def entity_asset_delete(self, entity_type, asset, request):
        # User Avatar
        if entity_type == FileAsset.EntityTypeContext.USER_AVATAR:
            user = User.objects.get(id=asset.user_id)
            user.avatar_asset_id = None
            user.save()
            return
        # User Cover
        if entity_type == FileAsset.EntityTypeContext.USER_COVER:
            user = User.objects.get(id=asset.user_id)
            user.cover_image_asset_id = None
            user.save()
            return
        return

    @asset_docs(
        operation_id="create_user_asset_upload",
        summary="Generate presigned URL for user asset upload",
        description="Generate presigned URL for user asset upload",
        request=OpenApiRequest(
            request=UserAssetUploadSerializer,
            examples=[
                OpenApiExample(
                    "User Avatar Upload",
                    value={
                        "name": "profile.jpg",
                        "type": "image/jpeg",
                        "size": 1024000,
                        "entity_type": "USER_AVATAR",
                    },
                    description="Example request for uploading a user avatar",
                ),
                OpenApiExample(
                    "User Cover Upload",
                    value={
                        "name": "cover.jpg",
                        "type": "image/jpeg",
                        "size": 1024000,
                        "entity_type": "USER_COVER",
                    },
                    description="Example request for uploading a user cover",
                ),
            ],
        ),
        responses={
            200: PRESIGNED_URL_SUCCESS_RESPONSE,
            400: VALIDATION_ERROR_RESPONSE,
            401: UNAUTHORIZED_RESPONSE,
        },
    )
    def post(self, request):
        """Generate presigned URL for user asset upload.

        Create a presigned URL for uploading user profile assets (avatar or cover image).
        This endpoint generates the necessary credentials for direct S3 upload.
        """
        entity_type = request.data.get("entity_type", False)

        #  Check if the entity type is allowed
        if not entity_type or entity_type not in ["USER_AVATAR", "USER_COVER"]:
            return Response(
                {"error": "Invalid entity type.", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            namespace=f"user-{request.user.id}",
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
            user=request.user,
            created_by=request.user,
            entity_type=entity_type,
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

    @asset_docs(
        operation_id="update_user_asset",
        summary="Mark user asset as uploaded",
        description="Mark user asset as uploaded",
        parameters=[ASSET_ID_PARAMETER],
        request=OpenApiRequest(
            request=AssetUpdateSerializer,
            examples=[
                OpenApiExample(
                    "Update Asset Attributes",
                    value={
                        "attributes": {
                            "name": "updated_profile.jpg",
                            "type": "image/jpeg",
                            "size": 1024000,
                        },
                        "entity_type": "USER_AVATAR",
                    },
                    description="Example request for updating asset attributes",
                ),
            ],
        ),
        responses={
            204: ASSET_UPDATED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
        },
    )
    def patch(self, request, asset_id):
        """Update user asset after upload completion.

        Update the asset status and attributes after the file has been uploaded to S3.
        This endpoint should be called after completing the S3 upload to mark the asset as uploaded.
        """
        asset = FileAsset.objects.filter(id=asset_id, user_id=request.user.id).first()
        if asset is None:
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            complete_asset_upload(asset_id=asset.id, storage=S3Storage(request=request))
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @asset_docs(
        operation_id="delete_user_asset",
        summary="Delete user asset",
        parameters=[ASSET_ID_PARAMETER],
        responses={
            204: ASSET_DELETED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
        },
    )
    def delete(self, request, asset_id):
        """Delete user asset.

        Delete a user profile asset (avatar or cover image) and remove its reference from the user profile.
        This performs a soft delete by marking the asset as deleted and updating the user's profile.
        """
        asset = FileAsset.objects.get(id=asset_id, user_id=request.user.id)
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        # get the entity and save the asset id for the request field
        self.entity_asset_delete(entity_type=asset.entity_type, asset=asset, request=request)
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserServerAssetEndpoint(BaseAPIView):
    """This endpoint is used to upload user profile images."""

    def asset_delete(self, asset_id):
        asset = FileAsset.objects.filter(id=asset_id).first()
        if asset is None:
            return
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return

    def entity_asset_delete(self, entity_type, asset, request):
        # User Avatar
        if entity_type == FileAsset.EntityTypeContext.USER_AVATAR:
            user = User.objects.get(id=asset.user_id)
            user.avatar_asset_id = None
            user.save()
            return
        # User Cover
        if entity_type == FileAsset.EntityTypeContext.USER_COVER:
            user = User.objects.get(id=asset.user_id)
            user.cover_image_asset_id = None
            user.save()
            return
        return

    @asset_docs(
        operation_id="create_user_server_asset_upload",
        summary="Generate presigned URL for user server asset upload",
        request=UserAssetUploadSerializer,
        responses={
            200: PRESIGNED_URL_SUCCESS_RESPONSE,
            400: VALIDATION_ERROR_RESPONSE,
        },
    )
    def post(self, request):
        """Generate presigned URL for user server asset upload.

        Create a presigned URL for uploading user profile assets
        (avatar or cover image) using server credentials. This endpoint generates the
        necessary credentials for direct S3 upload with server-side authentication.
        """
        entity_type = request.data.get("entity_type", False)

        #  Check if the entity type is allowed
        if not entity_type or entity_type not in ["USER_AVATAR", "USER_COVER"]:
            return Response(
                {"error": "Invalid entity type.", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            namespace=f"user-{request.user.id}",
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
            user=request.user,
            created_by=request.user,
            entity_type=entity_type,
        )

        # Get the presigned URL
        storage = S3Storage(request=request, is_server=True)
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

    @asset_docs(
        operation_id="update_user_server_asset",
        summary="Mark user server asset as uploaded",
        parameters=[ASSET_ID_PARAMETER],
        request=AssetUpdateSerializer,
        responses={
            204: ASSET_UPDATED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
        },
    )
    def patch(self, request, asset_id):
        """Update user server asset after upload completion.

        Update the asset status and attributes after the file has been uploaded to S3 using server credentials.
        This endpoint should be called after completing the S3 upload to mark the asset as uploaded.
        """
        asset = FileAsset.objects.filter(id=asset_id, user_id=request.user.id).first()
        if asset is None:
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            complete_asset_upload(
                asset_id=asset.id,
                storage=S3Storage(request=request, is_server=True),
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @asset_docs(
        operation_id="delete_user_server_asset",
        summary="Delete user server asset",
        parameters=[ASSET_ID_PARAMETER],
        responses={
            204: ASSET_DELETED_RESPONSE,
            404: NOT_FOUND_RESPONSE,
        },
    )
    def delete(self, request, asset_id):
        """Delete user server asset.

        Delete a user profile asset (avatar or cover image) using server credentials and
        remove its reference from the user profile. This performs a soft delete by marking the
        asset as deleted and updating the user's profile.
        """
        asset = FileAsset.objects.get(id=asset_id, user_id=request.user.id)
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        # get the entity and save the asset id for the request field
        self.entity_asset_delete(entity_type=asset.entity_type, asset=asset, request=request)
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class GenericAssetEndpoint(BaseAPIView):
    """This endpoint is used to upload generic assets that can be later bound to entities."""

    # The workspace is taken straight from the URL slug, so every method must
    # verify the caller is an active member of that workspace. Without this the
    # endpoint is a cross-workspace IDOR (the public-API sibling of the
    # CVE-2026-46558 dashboard fix).
    permission_classes = [WorkspaceUserPermission]

    use_read_replica = True

    @asset_docs(
        operation_id="get_generic_asset",
        summary="Get presigned URL for asset download",
        description="Get presigned URL for asset download",
        parameters=[WORKSPACE_SLUG_PARAMETER],
        responses={
            200: ASSET_DOWNLOAD_SUCCESS_RESPONSE,
            400: ASSET_DOWNLOAD_ERROR_RESPONSE,
            404: ASSET_NOT_FOUND_RESPONSE,
        },
    )
    def get(self, request, slug, asset_id):
        """Get presigned URL for asset download.

        Generate a presigned URL for downloading a generic asset.
        The asset must be uploaded and associated with the specified workspace.
        """
        try:
            # Get the workspace
            workspace = Workspace.objects.get(slug=slug)

            # Get the asset
            asset = FileAsset.objects.get(id=asset_id, workspace_id=workspace.id, is_deleted=False)
            if not can_read_file_asset(user_id=request.user.id, asset=asset):
                return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)

            # Check if the asset exists and is uploaded
            if not asset.is_uploaded:
                return Response(
                    {"error": "Asset not yet uploaded"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Generate presigned URL for GET.
            # Force attachment disposition for script-capable MIME types (e.g. SVG)
            # to prevent same-origin XSS when the asset URL shares the app's origin
            # (default MinIO self-hosted setup).
            storage = S3Storage(request=request, is_server=True)
            asset_mime_type = (asset.attributes.get("type") or "").split(";")[0].strip().lower()
            inline_types = set(RASTER_IMAGE_MIME_BY_EXTENSION.values())
            can_render_inline = (
                asset.upload_validation_version == UPLOAD_VALIDATION_VERSION and asset_mime_type in inline_types
            )
            disposition = "inline" if can_render_inline else "attachment"
            presigned_url = storage.generate_presigned_url(
                object_name=asset.asset.name,
                filename=asset.attributes.get("name"),
                disposition=disposition,
                content_type=(asset_mime_type if disposition == "inline" else "application/octet-stream"),
            )

            return Response(
                {
                    "asset_id": str(asset.id),
                    "asset_url": presigned_url,
                    "asset_name": asset.attributes.get("name", ""),
                    "asset_type": asset.attributes.get("type", ""),
                },
                status=status.HTTP_200_OK,
            )

        except Workspace.DoesNotExist:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)
        except FileAsset.DoesNotExist:
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            log_exception(e)
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @asset_docs(
        operation_id="create_generic_asset_upload",
        summary="Generate presigned URL for generic asset upload",
        description="Generate presigned URL for generic asset upload",
        parameters=[WORKSPACE_SLUG_PARAMETER],
        request=OpenApiRequest(
            request=GenericAssetUploadSerializer,
            examples=[
                OpenApiExample(
                    "GenericAssetUploadSerializer",
                    value={
                        "name": "image.jpg",
                        "type": "image/jpeg",
                        "size": 1024000,
                        "project_id": "123e4567-e89b-12d3-a456-426614174000",
                        "external_id": "1234567890",
                        "external_source": "github",
                    },
                    description="Example request for uploading a generic asset",
                ),
            ],
        ),
        responses={
            200: GENERIC_ASSET_UPLOAD_SUCCESS_RESPONSE,
            400: GENERIC_ASSET_VALIDATION_ERROR_RESPONSE,
            404: NOT_FOUND_RESPONSE,
            409: ASSET_CONFLICT_RESPONSE,
        },
    )
    def post(self, request, slug):
        """Generate presigned URL for generic asset upload.

        Create a presigned URL for uploading generic assets that can be bound to entities like work items.
        Supports various file types and includes external source tracking for integrations.
        """
        project_id = request.data.get("project_id")
        external_id = request.data.get("external_id")
        external_source = request.data.get("external_source")

        try:
            metadata = validate_upload_metadata(
                raw_name=request.data.get("name"),
                raw_size=request.data.get("size"),
                claimed_mime_type=request.data.get("type"),
                entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        # Get the workspace
        workspace = Workspace.objects.get(slug=slug)
        if project_id:
            project = Project.objects.filter(id=project_id, workspace=workspace).first()
            if (
                not project
                or not ProjectMember.objects.filter(
                    project=project,
                    workspace=workspace,
                    member=request.user,
                    is_active=True,
                ).exists()
            ):
                return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)

        asset_key = build_pending_asset_key(namespace=str(workspace.id), name=metadata.name)

        # Check for existing asset with same external details if provided
        if external_id and external_source:
            existing_assets = FileAsset.objects.filter(
                workspace__slug=slug,
                project_id=project_id,
                external_source=external_source,
                external_id=external_id,
                is_deleted=False,
            )
            if project_id is None:
                existing_assets = existing_assets.filter(created_by=request.user)
            existing_asset = existing_assets.first()

            if existing_asset and can_read_file_asset(
                user_id=request.user.id,
                asset=existing_asset,
            ):
                return Response(
                    {
                        "message": "Asset with same external id and source already exists",
                        "asset_id": str(existing_asset.id),
                        "asset_url": existing_asset.asset_url,
                    },
                    status=status.HTTP_409_CONFLICT,
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
            workspace_id=workspace.id,
            project_id=project_id,
            created_by=request.user,
            external_id=external_id,
            external_source=external_source,
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,  # Using ISSUE_ATTACHMENT since we'll bind it to issues # noqa: E501
        )

        # Get the presigned URL
        storage = S3Storage(request=request, is_server=True)
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

        return Response(
            {
                "upload_data": presigned_url,
                "asset_id": str(asset.id),
                "asset_url": asset.asset_url,
            },
            status=status.HTTP_200_OK,
        )

    @asset_docs(
        operation_id="update_generic_asset",
        summary="Update generic asset after upload completion",
        description="Update generic asset after upload completion",
        parameters=[WORKSPACE_SLUG_PARAMETER, ASSET_ID_PARAMETER],
        request=OpenApiRequest(
            request=GenericAssetUpdateSerializer,
            examples=[
                OpenApiExample(
                    "GenericAssetUpdateSerializer",
                    value={"is_uploaded": True},
                    description="Example request for updating a generic asset",
                )
            ],
        ),
        responses={
            204: ASSET_UPDATED_RESPONSE,
            404: ASSET_NOT_FOUND_RESPONSE,
        },
    )
    def patch(self, request, slug, asset_id):
        """Update generic asset after upload completion.

        Update the asset status after the file has been uploaded to S3.
        This endpoint should be called after completing the S3 upload to mark the asset as uploaded
        and trigger metadata extraction.
        """
        try:
            asset = FileAsset.objects.get(
                id=asset_id,
                workspace__slug=slug,
                created_by=request.user,
                is_deleted=False,
            )
            complete_asset_upload(
                asset_id=asset.id,
                storage=S3Storage(request=request, is_server=True),
            )

            return Response(status=status.HTTP_204_NO_CONTENT)
        except FileAsset.DoesNotExist:
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
