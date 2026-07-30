# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponseRedirect

# Third Party imports
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

# Module imports
from .. import BaseAPIView
from plane.app.serializers import IssueAttachmentSerializer
from plane.db.models import FileAsset, Issue, ProjectMember, Workspace
from plane.bgtasks.issue_activities_task import issue_activity
from plane.app.permissions import allow_permission, ROLE
from plane.settings.storage import S3Storage
from plane.utils.host import base_host
from plane.utils.file_asset_upload import (
    UPLOAD_URL_EXPIRATION_SECONDS,
    UploadError,
    build_pending_asset_key,
    complete_asset_upload,
    save_validated_multipart_asset,
    upload_error_payload,
    validate_multipart_upload,
    validate_upload_metadata,
)


class IssueAttachmentEndpoint(BaseAPIView):
    serializer_class = IssueAttachmentSerializer
    model = FileAsset
    parser_classes = (MultiPartParser, FormParser)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id, issue_id):
        issue = Issue.objects.filter(
            id=issue_id,
            workspace__slug=slug,
            project_id=project_id,
        ).first()
        if issue is None:
            return Response(
                {"error": "Issue not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        unexpected_fields = set(request.data) - {"asset"}
        if unexpected_fields:
            return Response(
                {
                    "error": "Legacy upload metadata is not accepted.",
                    "code": "unsupported_legacy_field",
                    "status": False,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        uploaded_file = request.FILES.get("asset")
        if uploaded_file is None:
            return Response(
                {"error": "A file is required.", "code": "missing_file", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            metadata = validate_multipart_upload(
                uploaded_file=uploaded_file,
                entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        workspace = Workspace.objects.get(slug=slug)
        try:
            asset = save_validated_multipart_asset(
                uploaded_file=uploaded_file,
                metadata=metadata,
                storage=S3Storage(request=request, is_server=True),
                namespace=workspace.id,
                created_by_id=request.user.id,
                entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
                entity_identifier=issue.id,
                workspace_id=workspace.id,
                project_id=project_id,
                issue_id=issue.id,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        serializer = IssueAttachmentSerializer(asset)
        issue_activity.delay(
            type="attachment.activity.created",
            requested_data=None,
            actor_id=str(self.request.user.id),
            issue_id=str(self.kwargs.get("issue_id", None)),
            project_id=str(self.kwargs.get("project_id", None)),
            current_instance=json.dumps(serializer.data, cls=DjangoJSONEncoder),
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN], creator=True, model=FileAsset)
    def delete(self, request, slug, project_id, issue_id, pk):
        issue_attachment = FileAsset.objects.filter(
            pk=pk, workspace__slug=slug, project_id=project_id, issue_id=issue_id
        ).first()
        if not issue_attachment:
            return Response(
                {"error": "Issue attachment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        issue_attachment.asset.delete(save=False)
        issue_attachment.delete()
        issue_activity.delay(
            type="attachment.activity.deleted",
            requested_data=None,
            actor_id=str(self.request.user.id),
            issue_id=str(self.kwargs.get("issue_id", None)),
            project_id=str(self.kwargs.get("project_id", None)),
            current_instance=None,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        issue_attachments = FileAsset.objects.filter(issue_id=issue_id, workspace__slug=slug, project_id=project_id)
        serializer = IssueAttachmentSerializer(issue_attachments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class IssueAttachmentV2Endpoint(BaseAPIView):
    serializer_class = IssueAttachmentSerializer
    model = FileAsset

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id, issue_id):
        if not Issue.objects.filter(
            id=issue_id,
            workspace__slug=slug,
            project_id=project_id,
        ).exists():
            return Response(
                {"error": "Issue not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
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

        asset_key = build_pending_asset_key(namespace=str(workspace.id), name=metadata.name)

        # Get the size limit
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
            created_by=request.user,
            issue_id=issue_id,
            project_id=project_id,
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
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
                "attachment": IssueAttachmentSerializer(asset).data,
                "asset_url": asset.asset_url,
            },
            status=status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN], creator=True, model=FileAsset)
    def delete(self, request, slug, project_id, issue_id, pk):
        issue_attachment = FileAsset.objects.get(pk=pk, workspace__slug=slug, project_id=project_id, issue_id=issue_id)
        issue_attachment.is_deleted = True
        issue_attachment.deleted_at = timezone.now()
        issue_attachment.save()

        issue_activity.delay(
            type="attachment.activity.deleted",
            requested_data=None,
            actor_id=str(self.request.user.id),
            issue_id=str(issue_id),
            project_id=str(project_id),
            current_instance=None,
            epoch=int(timezone.now().timestamp()),
            notification=True,
            origin=base_host(request=request, is_app=True),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id, pk=None):
        if pk:
            # Get the asset
            asset = FileAsset.objects.get(id=pk, workspace__slug=slug, project_id=project_id, issue_id=issue_id)

            # Check if the asset is uploaded
            if not asset.is_uploaded:
                return Response(
                    {"error": "The asset is not uploaded.", "status": False},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            storage = S3Storage(request=request)
            presigned_url = storage.generate_presigned_url(
                object_name=asset.asset.name,
                disposition="attachment",
                filename=asset.attributes.get("name"),
                content_type="application/octet-stream",
            )
            return HttpResponseRedirect(presigned_url)

        # Get all the attachments
        issue_attachments = FileAsset.objects.filter(
            issue_id=issue_id,
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
            workspace__slug=slug,
            project_id=project_id,
            is_uploaded=True,
        )
        # Serialize the attachments
        serializer = IssueAttachmentSerializer(issue_attachments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def patch(self, request, slug, project_id, issue_id, pk):
        issue_attachment = FileAsset.objects.filter(
            pk=pk, workspace__slug=slug, project_id=project_id, issue_id=issue_id
        ).first()
        if issue_attachment is None:
            return Response(
                {"error": "Issue attachment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_admin = ProjectMember.objects.filter(
            project_id=project_id,
            workspace__slug=slug,
            member=request.user,
            role=ROLE.ADMIN.value,
            is_active=True,
        ).exists()
        if issue_attachment.created_by_id != request.user.id and not is_admin:
            return Response(
                {"error": "Issue attachment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            storage = S3Storage(request=request)
            issue_attachment, completed, _ = complete_asset_upload(
                asset_id=issue_attachment.id,
                storage=storage,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        if completed:
            serializer = IssueAttachmentSerializer(issue_attachment)
            issue_activity.delay(
                type="attachment.activity.created",
                requested_data=None,
                actor_id=str(self.request.user.id),
                issue_id=str(self.kwargs.get("issue_id", None)),
                project_id=str(self.kwargs.get("project_id", None)),
                current_instance=json.dumps(serializer.data, cls=DjangoJSONEncoder),
                epoch=int(timezone.now().timestamp()),
                notification=True,
                origin=base_host(request=request, is_app=True),
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
