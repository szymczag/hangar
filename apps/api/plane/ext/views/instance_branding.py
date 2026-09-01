# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The logo shown on the sign-in page.

The text of the sign-in page goes through the ordinary configuration endpoint;
only the image needs its own handling, because it is a file. It is stored as a
FileAsset like every other image, with an entity type of its own so the public
static endpoint can serve it — the sign-in page is seen before anyone has an
account, so the logo has to be readable without a session.

That places it in the same category as user avatars: public, inline, and
therefore held to the same server-side raster validation rather than trusted
from the upload's own headers.
"""

# Django imports
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# Third party imports
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

# Module imports
from plane.app.views.base import BaseAPIView
from plane.authentication.session import BaseSessionAuthentication
from plane.db.models import FileAsset
from plane.license.api.permissions import InstanceAdminPermission
from plane.license.models import InstanceConfiguration
from plane.settings.storage import S3Storage
from plane.utils.cache import invalidate_cache
from plane.utils.file_asset_upload import (
    UploadError,
    save_validated_multipart_asset,
    upload_error_payload,
    validate_multipart_upload,
)

# Which stored pointer each uploadable image lives behind.
BRANDING_ASSETS = {
    "logo": ("INSTANCE_LOGO_ASSET_ID", FileAsset.EntityTypeContext.INSTANCE_LOGO),
    "login-background": (
        "INSTANCE_LOGIN_BACKGROUND_ASSET_ID",
        FileAsset.EntityTypeContext.INSTANCE_LOGIN_BACKGROUND,
    ),
    # PNG, JPEG, WebP or GIF only: the upload validator and the static asset
    # endpoint both refuse `.ico` and SVG, so the browser gets a raster icon and
    # legacy `/favicon.ico` requests keep hitting the built-in asset.
    "favicon": ("INSTANCE_FAVICON_ASSET_ID", FileAsset.EntityTypeContext.INSTANCE_FAVICON),
}


def _store_asset_id(key: str, value: str) -> None:
    InstanceConfiguration.objects.update_or_create(
        key=key,
        defaults={"value": value, "category": "BRANDING", "is_encrypted": False},
    )


class InstanceLogoEndpoint(BaseAPIView):
    """Upload or clear an image shown on the sign-in page."""

    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [InstanceAdminPermission]
    parser_classes = [MultiPartParser, FormParser]

    # The instance endpoint caches its answer for two hours, and the sign-in page
    # reads the logo from there. Without this an operator would upload a logo and
    # watch nothing happen until the cache expired.
    @invalidate_cache(path="/api/instances/", user=False)
    @invalidate_cache(path="/api/instances/configurations/", user=False)
    @method_decorator(csrf_protect)
    def post(self, request, kind="logo"):
        stored = BRANDING_ASSETS.get(kind)
        if stored is None:
            return Response({"error": "Unknown branding image."}, status=status.HTTP_404_NOT_FOUND)
        config_key, entity_type = stored

        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response({"error": "Attach an image to use as the logo."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            metadata = validate_multipart_upload(uploaded_file=uploaded_file, entity_type=entity_type)
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        try:
            asset = save_validated_multipart_asset(
                uploaded_file=uploaded_file,
                metadata=metadata,
                storage=S3Storage(request=request, is_server=True),
                namespace="instance",
                created_by_id=request.user.id,
                entity_type=entity_type,
                entity_identifier=None,
            )
        except UploadError as error:
            return Response(upload_error_payload(error), status=error.http_status)

        _store_asset_id(config_key, str(asset.id))
        return Response({"asset_id": str(asset.id), "asset_url": asset.asset_url}, status=status.HTTP_201_CREATED)

    @invalidate_cache(path="/api/instances/", user=False)
    @invalidate_cache(path="/api/instances/configurations/", user=False)
    @method_decorator(csrf_protect)
    def delete(self, request, kind="logo"):
        """Return to the built-in appearance.

        The asset row is left alone: clearing the pointer is enough to stop
        serving it, and deleting stored objects from here would make an
        accidental click unrecoverable.
        """
        stored = BRANDING_ASSETS.get(kind)
        if stored is None:
            return Response({"error": "Unknown branding image."}, status=status.HTTP_404_NOT_FOUND)
        _store_asset_id(stored[0], "")
        return Response(status=status.HTTP_204_NO_CONTENT)
