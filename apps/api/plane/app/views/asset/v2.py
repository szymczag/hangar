# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import uuid

# Django imports
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.db.models import Q

# Third party imports
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

# Module imports
from ..base import BaseAPIView
from plane.db.models import (
    DeployBoard,
    DraftIssue,
    FileAsset,
    Issue,
    IssueComment,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    User,
    Workspace,
    WorkspaceMember,
)
from plane.settings.storage import S3Storage
from plane.app.permissions import allow_permission, ROLE
from plane.utils.cache import invalidate_cache_directly
from plane.throttles.asset import AssetRateThrottle
from plane.utils.path_validator import sanitize_filename
from plane.utils.file_asset_upload import (
    UPLOAD_URL_EXPIRATION_SECONDS,
    UPLOAD_VALIDATION_VERSION,
    UploadError,
    build_pending_asset_key,
    complete_asset_upload,
    upload_error_payload,
    validate_upload_metadata,
)
from plane.utils.file_asset_permissions import (
    can_manage_project_cover,
    can_mutate_file_asset,
    can_read_file_asset,
    is_workspace_asset_admin,
)


class UserAssetsV2Endpoint(BaseAPIView):
    """This endpoint is used to upload user profile images."""

    def asset_delete(self, asset_id):
        asset = FileAsset.objects.filter(id=asset_id).first()
        if asset is None:
            return
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return

    def entity_asset_save(self, asset_id, entity_type, asset, request):
        # User Avatar
        if entity_type == FileAsset.EntityTypeContext.USER_AVATAR:
            user = User.objects.get(id=asset.user_id)
            user.avatar = ""
            # Delete the previous avatar
            if user.avatar_asset_id:
                self.asset_delete(user.avatar_asset_id)
            # Save the new avatar
            user.avatar_asset_id = asset_id
            user.save()
            invalidate_cache_directly(path="/api/users/me/", url_params=False, user=True, request=request)
            invalidate_cache_directly(
                path="/api/users/me/settings/",
                url_params=False,
                user=True,
                request=request,
            )
            return
        # User Cover
        if entity_type == FileAsset.EntityTypeContext.USER_COVER:
            user = User.objects.get(id=asset.user_id)
            user.cover_image = None
            # Delete the previous cover image
            if user.cover_image_asset_id:
                self.asset_delete(user.cover_image_asset_id)
            # Save the new cover image
            user.cover_image_asset_id = asset_id
            user.save()
            invalidate_cache_directly(path="/api/users/me/", url_params=False, user=True, request=request)
            invalidate_cache_directly(
                path="/api/users/me/settings/",
                url_params=False,
                user=True,
                request=request,
            )
            return
        return

    def entity_asset_delete(self, entity_type, asset, request):
        # User Avatar
        if entity_type == FileAsset.EntityTypeContext.USER_AVATAR:
            user = User.objects.get(id=asset.user_id)
            user.avatar_asset_id = None
            user.save()
            invalidate_cache_directly(path="/api/users/me/", url_params=False, user=True, request=request)
            invalidate_cache_directly(
                path="/api/users/me/settings/",
                url_params=False,
                user=True,
                request=request,
            )
            return
        # User Cover
        if entity_type == FileAsset.EntityTypeContext.USER_COVER:
            user = User.objects.get(id=asset.user_id)
            user.cover_image_asset_id = None
            user.save()
            invalidate_cache_directly(path="/api/users/me/", url_params=False, user=True, request=request)
            invalidate_cache_directly(
                path="/api/users/me/settings/",
                url_params=False,
                user=True,
                request=request,
            )
            return
        return

    def post(self, request):
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

    def patch(self, request, asset_id):
        asset = FileAsset.objects.filter(id=asset_id, user_id=request.user.id).first()
        if asset is None:
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            asset, completed, _ = complete_asset_upload(
                asset_id=asset.id,
                storage=S3Storage(request=request),
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        if not completed:
            return Response(status=status.HTTP_204_NO_CONTENT)

        # get the entity and save the asset id for the request field
        self.entity_asset_save(
            asset_id=asset_id,
            entity_type=asset.entity_type,
            asset=asset,
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, asset_id):
        asset = FileAsset.objects.get(id=asset_id, user_id=request.user.id)
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        # get the entity and save the asset id for the request field
        self.entity_asset_delete(entity_type=asset.entity_type, asset=asset, request=request)
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceFileAssetEndpoint(BaseAPIView):
    """This endpoint is used to upload cover images/logos etc for workspace, projects and users."""

    def get_scoped_entity_fields(self, *, request, workspace, entity_type, entity_id):
        if entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
            return {"workspace_id": workspace.id} if str(entity_id) == str(workspace.id) else None
        if entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
            project = Project.objects.filter(id=entity_id, workspace=workspace).first()
            if project and can_manage_project_cover(
                user_id=request.user.id,
                workspace_id=workspace.id,
                project_id=project.id,
            ):
                return {"project_id": project.id}
            return None
        if entity_type in {
            FileAsset.EntityTypeContext.USER_AVATAR,
            FileAsset.EntityTypeContext.USER_COVER,
        }:
            return {"user_id": request.user.id} if str(entity_id) == str(request.user.id) else None
        if entity_type == FileAsset.EntityTypeContext.PAGE_DESCRIPTION:
            page = Page.objects.filter(
                id=entity_id,
                workspace=workspace,
            ).first()
            if page is None:
                return None
            if page.owned_by_id == request.user.id:
                return {"page_id": page.id}
            if page.access != Page.PUBLIC_ACCESS:
                return None
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
            if accessible_project:
                return {
                    "page_id": page.id,
                    "project_id": accessible_project,
                }
            return None
        return None

    def asset_delete(self, asset_id):
        asset = FileAsset.objects.filter(id=asset_id).first()
        # Check if the asset exists
        if asset is None:
            return
        # Mark the asset as deleted
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return

    def entity_asset_save(self, asset_id, entity_type, asset, request):
        # Workspace Logo
        if entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
            workspace = Workspace.objects.filter(id=asset.workspace_id).first()
            if workspace is None:
                return
            # Delete the previous logo
            if workspace.logo_asset_id:
                self.asset_delete(workspace.logo_asset_id)
            # Save the new logo
            workspace.logo = ""
            workspace.logo_asset_id = asset_id
            workspace.save()
            invalidate_cache_directly(path="/api/workspaces/", url_params=False, user=False, request=request)
            invalidate_cache_directly(
                path="/api/users/me/workspaces/",
                url_params=False,
                user=True,
                request=request,
            )
            invalidate_cache_directly(path="/api/instances/", url_params=False, user=False, request=request)
            return

        # Project Cover
        elif entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
            project = Project.objects.filter(id=asset.project_id).first()
            if project is None:
                return
            # Delete the previous cover image
            if project.cover_image_asset_id:
                self.asset_delete(project.cover_image_asset_id)
            # Save the new cover image
            project.cover_image = ""
            project.cover_image_asset_id = asset_id
            project.save()
            return
        else:
            return

    def entity_asset_delete(self, entity_type, asset, request):
        # Workspace Logo
        if entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
            workspace = Workspace.objects.get(id=asset.workspace_id)
            if workspace is None:
                return
            workspace.logo_asset_id = None
            workspace.save()
            invalidate_cache_directly(path="/api/workspaces/", url_params=False, user=False, request=request)
            invalidate_cache_directly(
                path="/api/users/me/workspaces/",
                url_params=False,
                user=True,
                request=request,
            )
            invalidate_cache_directly(path="/api/instances/", url_params=False, user=False, request=request)
            return
        # Project Cover
        elif entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
            project = Project.objects.filter(id=asset.project_id).first()
            if project is None:
                return
            project.cover_image_asset_id = None
            project.save()
            return
        else:
            return

    def has_project_asset_access(self, request, asset):
        """Return whether the user may access a workspace-scoped asset.

        This endpoint is authorized at the WORKSPACE level, so a workspace
        member/guest could otherwise reach an asset that belongs to a project
        they are not a member of. For project-bound assets, require an active
        ProjectMember of the asset's project. Workspace-level entity types
        (WORKSPACE_LOGO, USER_AVATAR, USER_COVER) have project_id=None and are
        always allowed.
        """
        if asset.project_id is None:
            return True
        # Scope the membership lookup to the asset's workspace as well as its
        # project, mirroring allow_permission's PROJECT branch. This prevents a
        # member of the same project in a different workspace from passing the
        # check should an asset row ever be inconsistent (asset.workspace_id !=
        # asset.project.workspace_id).
        return ProjectMember.objects.filter(
            member=request.user,
            workspace_id=asset.workspace_id,
            project_id=asset.project_id,
            is_active=True,
        ).exists()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request, slug):
        entity_type = request.data.get("entity_type")
        entity_identifier = request.data.get("entity_identifier", False)
        workspace = Workspace.objects.get(slug=slug)

        # Check if the entity type is allowed
        if entity_type not in FileAsset.EntityTypeContext.values:
            return Response(
                {"error": "Invalid entity type.", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # WORKSPACE_LOGO may only be uploaded by workspace admins
        if entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
            workspace_member = WorkspaceMember.objects.filter(
                workspace__slug=slug, member=request.user, is_active=True
            ).first()
            if not workspace_member or workspace_member.role != ROLE.ADMIN.value:
                return Response(
                    {"error": "Only workspace admins can upload a workspace logo."},
                    status=status.HTTP_403_FORBIDDEN,
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

        entity_fields = self.get_scoped_entity_fields(
            request=request,
            workspace=workspace,
            entity_type=entity_type,
            entity_id=entity_identifier,
        )
        if entity_fields is None:
            return Response(
                {"error": "Invalid entity context.", "status": False},
                status=status.HTTP_404_NOT_FOUND,
            )

        # asset key
        asset_key = build_pending_asset_key(namespace=str(workspace.id), name=metadata.name)

        # Create a File Asset
        asset = FileAsset.objects.create(
            attributes={
                "name": metadata.name,
                "type": metadata.mime_type,
                "size": metadata.size,
            },
            asset=asset_key,
            size=metadata.size,
            workspace=workspace,
            created_by=request.user,
            entity_type=entity_type,
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

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def patch(self, request, slug, asset_id):
        asset = FileAsset.objects.filter(id=asset_id, workspace__slug=slug).first()
        if asset is None:
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        # enforce project-level access for project-bound assets
        if not self.has_project_asset_access(request, asset):
            return Response(
                {"error": "You don't have access to this asset."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_mutate_file_asset(user_id=request.user.id, asset=asset):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            asset, completed, _ = complete_asset_upload(
                asset_id=asset.id,
                storage=S3Storage(request=request),
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        if not completed:
            return Response(status=status.HTTP_204_NO_CONTENT)

        # get the entity and save the asset id for the request field
        self.entity_asset_save(
            asset_id=asset_id,
            entity_type=asset.entity_type,
            asset=asset,
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def delete(self, request, slug, asset_id):
        asset = FileAsset.objects.filter(id=asset_id, workspace__slug=slug).first()
        if asset is None:
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        # enforce project-level access for project-bound assets
        if not self.has_project_asset_access(request, asset):
            return Response(
                {"error": "You don't have access to this asset."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_mutate_file_asset(user_id=request.user.id, asset=asset):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        # get the entity and save the asset id for the request field
        self.entity_asset_delete(entity_type=asset.entity_type, asset=asset, request=request)
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, asset_id):
        # get the asset id
        asset = FileAsset.objects.get(id=asset_id, workspace__slug=slug)
        # enforce project-level access for project-bound assets
        if not self.has_project_asset_access(request, asset):
            return Response(
                {"error": "You don't have access to this asset."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not can_read_file_asset(user_id=request.user.id, asset=asset):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if the asset is uploaded
        if not asset.is_uploaded:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the presigned URL
        storage = S3Storage(request=request)
        # Generate a presigned URL to share an S3 object
        signed_url = storage.generate_presigned_url(
            object_name=asset.asset.name,
            disposition="attachment",
            filename=asset.attributes.get("name"),
            content_type="application/octet-stream",
        )
        # Redirect to the signed URL
        return HttpResponseRedirect(signed_url)


class StaticFileAssetEndpoint(BaseAPIView):
    """This endpoint is used to get the signed URL for a static asset."""

    permission_classes = [AllowAny]

    @staticmethod
    def _may_read_organisation_asset(request, asset):
        """Gate workspace logos and project covers; leave user imagery public.

        A project cover stays public while the project is published, because the
        public board lists it (plane/space/views/project.py). Workspace logos
        have no such consumer, so they simply require membership.
        """
        if asset.entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO:
            return (
                request.user.is_authenticated
                and WorkspaceMember.objects.filter(
                    workspace_id=asset.workspace_id, member=request.user, is_active=True
                ).exists()
            )

        if asset.entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
            if asset.project_id and DeployBoard.objects.filter(
                project_id=asset.project_id, entity_name="project", is_disabled=False
            ).exists():
                return True
            return (
                request.user.is_authenticated
                and asset.project_id is not None
                and ProjectMember.objects.filter(
                    project_id=asset.project_id, member=request.user, is_active=True
                ).exists()
            )

        return True

    def get(self, request, asset_id):
        # get the asset id
        asset = FileAsset.objects.get(id=asset_id)

        # Check if the asset is uploaded
        if not asset.is_uploaded:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Check if the entity type is allowed
        if asset.entity_type not in [
            FileAsset.EntityTypeContext.USER_AVATAR,
            FileAsset.EntityTypeContext.USER_COVER,
            FileAsset.EntityTypeContext.WORKSPACE_LOGO,
            FileAsset.EntityTypeContext.PROJECT_COVER,
            FileAsset.EntityTypeContext.INSTANCE_LOGO,
            FileAsset.EntityTypeContext.INSTANCE_LOGIN_BACKGROUND,
        ]:
            return Response(
                {"error": "Invalid entity type.", "status": False},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Static assets are public and inline, so only server-validated raster
        # content carrying the current validation marker is eligible.
        if asset.upload_validation_version == 0:
            try:
                from plane.bgtasks.file_asset_task import enqueue_legacy_static_revalidation

                enqueue_legacy_static_revalidation(asset.id)
            except Exception:
                pass
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if asset.upload_validation_version != UPLOAD_VALIDATION_VERSION:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        asset_mime_type = (asset.attributes.get("type") or "").split(";")[0].strip().lower()
        if asset_mime_type not in {
            "image/gif",
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Checked here, immediately before a URL would be handed out, so the
        # legacy-revalidation path above keeps running for assets nobody may
        # read. Avatars and user covers stay reachable without a session — they
        # are rendered on sign-in screens and public boards alike. Organisation
        # imagery is different: a workspace logo names a company and a project
        # cover names a project, and neither should be retrievable by anyone who
        # merely holds an asset id.
        if not self._may_read_organisation_asset(request, asset):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Generate a presigned URL to share an S3 object
        storage = S3Storage(request=request)
        signed_url = storage.generate_presigned_url(
            object_name=asset.asset.name,
            disposition="inline",
            content_type=asset_mime_type,
        )
        # Redirect to the signed URL
        return HttpResponseRedirect(signed_url)


class AssetRestoreEndpoint(BaseAPIView):
    """Endpoint to restore a deleted assets."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request, slug, asset_id):
        asset = FileAsset.all_objects.filter(id=asset_id, workspace__slug=slug).first()
        if asset is None or not can_mutate_file_asset(user_id=request.user.id, asset=asset):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        asset.is_deleted = False
        asset.deleted_at = None
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectAssetEndpoint(BaseAPIView):
    """This endpoint is used to upload cover images/logos etc for workspace, projects and users."""

    def get_scoped_entity_fields(self, *, request, workspace, project_id, entity_type, entity_id):
        if entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
            can_manage_cover = can_manage_project_cover(
                user_id=request.user.id,
                workspace_id=workspace.id,
                project_id=project_id,
            )
            # Project-scoped callers already persist the route project_id.
            return {} if can_manage_cover and str(entity_id) == str(project_id) else None
        if entity_type in {
            FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
            FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
        }:
            issue = Issue.objects.filter(
                id=entity_id,
                workspace=workspace,
                project_id=project_id,
            ).first()
            return {"issue_id": issue.id} if issue else None
        if entity_type == FileAsset.EntityTypeContext.COMMENT_DESCRIPTION:
            comment = IssueComment.objects.filter(
                id=entity_id,
                workspace=workspace,
                project_id=project_id,
            ).first()
            return {"comment_id": comment.id} if comment else None
        if entity_type == FileAsset.EntityTypeContext.PAGE_DESCRIPTION:
            page = Page.objects.filter(
                Q(owned_by=request.user) | Q(access=Page.PUBLIC_ACCESS),
                id=entity_id,
                workspace=workspace,
                project_pages__project_id=project_id,
                project_pages__deleted_at__isnull=True,
            ).first()
            return {"page_id": page.id} if page else None
        if entity_type == FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION:
            draft_issue = DraftIssue.objects.filter(
                id=entity_id,
                workspace=workspace,
                project_id=project_id,
                created_by=request.user,
            ).first()
            return {"draft_issue_id": draft_issue.id} if draft_issue else None
        return None

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id):
        entity_type = request.data.get("entity_type", "")
        entity_identifier = request.data.get("entity_identifier")

        # Check if the entity type is allowed
        if entity_type not in FileAsset.EntityTypeContext.values:
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

        # Get the workspace
        workspace = Workspace.objects.get(slug=slug)
        entity_fields = self.get_scoped_entity_fields(
            request=request,
            workspace=workspace,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_identifier,
        )
        if entity_fields is None:
            return Response(
                {"error": "Invalid entity context.", "status": False},
                status=status.HTTP_404_NOT_FOUND,
            )

        # asset key
        asset_key = build_pending_asset_key(namespace=str(workspace.id), name=metadata.name)

        # Create a File Asset
        asset = FileAsset.objects.create(
            attributes={
                "name": metadata.name,
                "type": metadata.mime_type,
                "size": metadata.size,
            },
            asset=asset_key,
            size=metadata.size,
            workspace=workspace,
            created_by=request.user,
            entity_type=entity_type,
            project_id=project_id,
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

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def patch(self, request, slug, project_id, pk):
        asset = FileAsset.objects.filter(
            id=pk,
            workspace__slug=slug,
            project_id=project_id,
        ).first()
        if asset is None:
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        if not can_mutate_file_asset(user_id=request.user.id, asset=asset):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            complete_asset_upload(asset_id=asset.id, storage=S3Storage(request=request))
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def delete(self, request, slug, project_id, pk):
        asset = FileAsset.objects.filter(id=pk, workspace__slug=slug, project_id=project_id).first()
        if asset is None or not can_mutate_file_asset(user_id=request.user.id, asset=asset):
            return Response({"error": "Asset not found."}, status=status.HTTP_404_NOT_FOUND)
        # Check deleted assets
        asset.is_deleted = True
        asset.deleted_at = timezone.now()
        # Save the asset
        asset.save(update_fields=["is_deleted", "deleted_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, pk):
        # get the asset id
        asset = FileAsset.objects.get(workspace__slug=slug, project_id=project_id, pk=pk)
        if not can_read_file_asset(user_id=request.user.id, asset=asset):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if the asset is uploaded
        if not asset.is_uploaded:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get the presigned URL
        storage = S3Storage(request=request)
        # Generate a presigned URL to share an S3 object
        signed_url = storage.generate_presigned_url(
            object_name=asset.asset.name,
            disposition="attachment",
            filename=asset.attributes.get("name"),
        )
        # Redirect to the signed URL
        return HttpResponseRedirect(signed_url)


class ProjectBulkAssetEndpoint(BaseAPIView):
    def save_project_cover(self, asset, project_id):
        project = Project.objects.get(id=project_id)
        project.cover_image_asset_id = asset.id
        project.save()

    def has_locked_project_cover_access(self, *, request, workspace, project_id):
        """Recheck the role under a row lock before changing shared project state."""

        workspace_admin = WorkspaceMember.objects.select_for_update().filter(
            workspace=workspace,
            member=request.user,
            role=ROLE.ADMIN.value,
            is_active=True,
        )
        project_manager = ProjectMember.objects.select_for_update().filter(
            project_id=project_id,
            workspace=workspace,
            member=request.user,
            role__in=[ROLE.ADMIN.value, ROLE.MEMBER.value],
            is_active=True,
        )
        return workspace_admin.exists() or project_manager.exists()

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def post(self, request, slug, project_id, entity_id):
        asset_ids = request.data.get("asset_ids", [])

        if not isinstance(asset_ids, list) or not asset_ids:
            return Response({"error": "No asset ids provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            normalized_asset_ids = {uuid.UUID(str(asset_id)) for asset_id in asset_ids}
        except (TypeError, ValueError, AttributeError):
            return Response({"error": "Invalid asset ids."}, status=status.HTTP_400_BAD_REQUEST)
        if len(normalized_asset_ids) != len(asset_ids):
            return Response({"error": "Duplicate asset ids."}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve every requested object under the caller/workspace/project
        # boundary. A partial match must fail closed.
        assets = FileAsset.objects.filter(
            id__in=normalized_asset_ids,
            workspace__slug=slug,
            created_by=request.user,
            is_uploaded=True,
        ).filter(Q(project_id=project_id) | Q(project_id__isnull=True))
        resolved_assets = list(assets)

        if len(resolved_assets) != len(normalized_asset_ids):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        entity_types = {asset.entity_type for asset in resolved_assets}
        if len(entity_types) != 1:
            return Response(
                {"error": "Assets must have the same entity type."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entity_type = entity_types.pop()
        workspace = Workspace.objects.get(slug=slug)
        entity_fields = ProjectAssetEndpoint.get_scoped_entity_fields(
            self,
            request=request,
            workspace=workspace,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        if entity_fields is None:
            return Response(
                {"error": "Invalid entity context."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if entity_type == FileAsset.EntityTypeContext.PROJECT_COVER and len(resolved_assets) != 1:
            return Response(
                {"error": "Only one project cover can be associated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                if entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
                    if not self.has_locked_project_cover_access(
                        request=request,
                        workspace=workspace,
                        project_id=project_id,
                    ):
                        return Response(
                            {"error": "Invalid entity context."},
                            status=status.HTTP_404_NOT_FOUND,
                        )
                    Project.objects.select_for_update().get(id=project_id, workspace=workspace)
                update_fields = {"project_id": project_id, **entity_fields}
                assets.update(**update_fields)
                if entity_type == FileAsset.EntityTypeContext.PROJECT_COVER:
                    self.save_project_cover(resolved_assets[0], project_id)
        except IntegrityError:
            return Response(
                {"error": "The target entity is no longer available."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetCheckEndpoint(BaseAPIView):
    """Endpoint to check if an asset exists."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, asset_id):
        asset = FileAsset.objects.filter(
            id=asset_id,
            workspace__slug=slug,
            deleted_at__isnull=True,
        ).first()
        exists = bool(asset and can_read_file_asset(user_id=request.user.id, asset=asset))
        return Response({"exists": exists}, status=status.HTTP_200_OK)


class DuplicateAssetEndpoint(BaseAPIView):
    throttle_classes = [AssetRateThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def post(self, request, slug, asset_id):
        project_id = request.data.get("project_id", None)
        entity_id = request.data.get("entity_id", None)
        entity_type = request.data.get("entity_type", None)

        if not entity_type or entity_type not in FileAsset.EntityTypeContext.values:
            return Response(
                {"error": "Invalid entity type or entity id"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        workspace = Workspace.objects.get(slug=slug)
        if project_id:
            if not ProjectMember.objects.filter(
                project_id=project_id,
                workspace=workspace,
                member=request.user,
                is_active=True,
            ).exists():
                return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
            entity_fields = ProjectAssetEndpoint.get_scoped_entity_fields(
                self,
                request=request,
                workspace=workspace,
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        else:
            if entity_type == FileAsset.EntityTypeContext.WORKSPACE_LOGO and not is_workspace_asset_admin(
                user_id=request.user.id,
                workspace_id=workspace.id,
            ):
                return Response({"error": "Invalid entity context."}, status=status.HTTP_404_NOT_FOUND)
            entity_fields = WorkspaceFileAssetEndpoint.get_scoped_entity_fields(
                self,
                request=request,
                workspace=workspace,
                entity_type=entity_type,
                entity_id=entity_id,
            )
        if entity_fields is None:
            return Response({"error": "Invalid entity context."}, status=status.HTTP_404_NOT_FOUND)

        storage = S3Storage(request=request)
        # Only copy a server-validated immutable source from this workspace.
        original_asset = FileAsset.objects.filter(
            id=asset_id,
            is_uploaded=True,
            workspace=workspace,
            upload_validation_version=UPLOAD_VALIDATION_VERSION,
        ).first()

        if not original_asset:
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_read_file_asset(user_id=request.user.id, asset=original_asset):
            return Response({"error": "Asset not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            metadata = validate_upload_metadata(
                raw_name=(original_asset.attributes or {}).get("name"),
                raw_size=original_asset.size,
                claimed_mime_type=(original_asset.attributes or {}).get("type"),
                entity_type=entity_type,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        source_metadata = storage.get_object_metadata(original_asset.asset.name)
        source_etag = (source_metadata or {}).get("ETag")
        if not source_etag:
            return Response(
                {"error": "File storage is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        sanitized_name = sanitize_filename(metadata.name) or "unnamed"
        destination_key = f"{workspace.id}/{uuid.uuid4().hex}-{sanitized_name}"
        copied = storage.copy_object(
            original_asset.asset.name,
            destination_key,
            source_etag=source_etag,
            content_type=metadata.mime_type,
        )
        final_metadata = storage.get_object_metadata(destination_key) if copied else None
        final_type = ((final_metadata or {}).get("ContentType") or "").split(";", 1)[0].strip().lower()
        if (
            final_metadata is None
            or final_metadata.get("ContentLength") != metadata.size
            or final_type != metadata.mime_type
        ):
            storage.delete_files([destination_key])
            return Response(
                {"error": "File storage is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        create_fields = {"workspace_id": workspace.id, "project_id": project_id, **entity_fields}
        try:
            duplicated_asset = FileAsset.objects.create(
                attributes={
                    "name": metadata.name,
                    "type": metadata.mime_type,
                    "size": metadata.size,
                },
                asset=destination_key,
                size=metadata.size,
                created_by_id=request.user.id,
                entity_type=entity_type,
                storage_metadata={
                    **final_metadata,
                    "DetectedContentType": (original_asset.storage_metadata or {}).get(
                        "DetectedContentType",
                        metadata.mime_type,
                    ),
                    "ValidatedAt": timezone.now().isoformat(),
                    "ValidationVersion": UPLOAD_VALIDATION_VERSION,
                    "ValidationSource": "validated-asset-copy",
                },
                is_uploaded=True,
                upload_validation_version=UPLOAD_VALIDATION_VERSION,
                **create_fields,
            )
        except Exception:
            storage.delete_files([destination_key])
            raise
        return Response({"asset_id": str(duplicated_asset.id)}, status=status.HTTP_200_OK)


class WorkspaceAssetDownloadEndpoint(BaseAPIView):
    """Endpoint to generate a download link for an asset with content-disposition=attachment."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="WORKSPACE")
    def get(self, request, slug, asset_id):
        try:
            asset = FileAsset.objects.get(
                id=asset_id,
                workspace__slug=slug,
                is_uploaded=True,
            )
        except FileAsset.DoesNotExist:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not can_read_file_asset(user_id=request.user.id, asset=asset):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        storage = S3Storage(request=request)
        signed_url = storage.generate_presigned_url(
            object_name=asset.asset.name,
            disposition="attachment",
            filename=asset.attributes.get("name", uuid.uuid4().hex),
            content_type="application/octet-stream",
        )

        return HttpResponseRedirect(signed_url)


class ProjectAssetDownloadEndpoint(BaseAPIView):
    """Endpoint to generate a download link for an asset with content-disposition=attachment."""

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST], level="PROJECT")
    def get(self, request, slug, project_id, asset_id):
        try:
            asset = FileAsset.objects.get(
                id=asset_id,
                workspace__slug=slug,
                project_id=project_id,
                is_uploaded=True,
            )
        except FileAsset.DoesNotExist:
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not can_read_file_asset(user_id=request.user.id, asset=asset):
            return Response(
                {"error": "The requested asset could not be found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        storage = S3Storage(request=request)
        signed_url = storage.generate_presigned_url(
            object_name=asset.asset.name,
            disposition="attachment",
            filename=asset.attributes.get("name", uuid.uuid4().hex),
            content_type="application/octet-stream",
        )

        return HttpResponseRedirect(signed_url)
