# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Server-side policy and validation for direct-to-object-storage uploads."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import PurePath

import magic
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from plane.db.models import FileAsset
from plane.utils.path_validator import sanitize_filename

logger = logging.getLogger(__name__)

UPLOAD_SIGNATURE_BYTES = 64 * 1024
UPLOAD_URL_EXPIRATION_SECONDS = 10 * 60
UPLOAD_VALIDATION_VERSION = 1
UPLOAD_VALIDATION_REJECTED = -1

RASTER_IMAGE_MIME_BY_EXTENSION = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

ATTACHMENT_MIME_BY_EXTENSION = {
    **RASTER_IMAGE_MIME_BY_EXTENSION,
    ".7z": "application/x-7z-compressed",
    ".aac": "audio/aac",
    ".avi": "video/x-msvideo",
    ".bmp": "image/bmp",
    ".csv": "text/csv",
    ".css": "text/css",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".flac": "audio/flac",
    ".gif": "image/gif",
    ".glb": "model/gltf-binary",
    ".gltf": "model/gltf+json",
    ".gz": "application/gzip",
    ".json": "application/json",
    ".js": "text/javascript",
    ".m4a": "audio/x-m4a",
    ".markdown": "text/markdown",
    ".md": "text/markdown",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".obj": "model/obj",
    ".odb": "application/vnd.oasis.opendocument.database",
    ".odg": "application/vnd.oasis.opendocument.graphics",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ogg": "audio/ogg",
    ".ogv": "video/ogg",
    ".otf": "font/otf",
    ".pbm": "image/x-portable-bitmap",
    ".pdf": "application/pdf",
    ".pgm": "image/x-portable-graymap",
    ".png": "image/png",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppm": "image/x-portable-pixmap",
    ".rar": "application/x-rar-compressed",
    ".rtf": "application/rtf",
    ".sql": "application/x-sql",
    ".svg": "image/svg+xml",
    ".tar": "application/x-tar",
    ".tgz": "application/gzip",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".ttf": "font/ttf",
    ".txt": "text/plain",
    ".vsd": "application/vnd.visio",
    ".vsdx": "application/vnd.visio",
    ".wav": "audio/wav",
    ".webm": "video/webm",
    ".wmv": "video/x-ms-wmv",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xml": "application/xml",
    ".zip": "application/zip",
}

TEXT_MIME_TYPES = {
    "application/json",
    "application/x-sql",
    "image/svg+xml",
    "model/gltf+json",
    "model/obj",
    "text/css",
    "text/csv",
    "text/javascript",
    "text/markdown",
    "text/plain",
    "application/xml",
}

# libmagic intentionally reports container/family types for several formats.
MIME_EQUIVALENCE_GROUPS = (
    frozenset(
        {
            "application/zip",
            "application/x-zip",
            "application/x-zip-compressed",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.database",
            "application/vnd.oasis.opendocument.graphics",
            "application/vnd.oasis.opendocument.presentation",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.visio",
        }
    ),
    frozenset(
        {
            "application/x-ole-storage",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "application/msword",
        }
    ),
    frozenset({"application/gzip", "application/x-gzip"}),
    frozenset({"application/x-rar", "application/x-rar-compressed"}),
    frozenset({"application/rtf", "text/rtf"}),
    frozenset({"audio/midi", "audio/x-midi"}),
    frozenset({"audio/wav", "audio/x-wav"}),
    frozenset({"audio/m4a", "audio/mp4", "audio/x-m4a", "video/mp4"}),
    frozenset({"application/javascript", "text/javascript"}),
    frozenset({"font/otf", "font/sfnt"}),
    frozenset({"font/ttf", "font/sfnt"}),
    frozenset({"application/xml", "text/xml", "image/svg+xml"}),
)

INLINE_IMAGE_ENTITY_TYPES = {
    FileAsset.EntityTypeContext.COMMENT_DESCRIPTION,
    FileAsset.EntityTypeContext.DRAFT_ISSUE_DESCRIPTION,
    FileAsset.EntityTypeContext.ISSUE_DESCRIPTION,
    FileAsset.EntityTypeContext.PAGE_DESCRIPTION,
    FileAsset.EntityTypeContext.PROJECT_COVER,
    FileAsset.EntityTypeContext.USER_AVATAR,
    FileAsset.EntityTypeContext.USER_COVER,
    FileAsset.EntityTypeContext.WORKSPACE_LOGO,
    FileAsset.EntityTypeContext.INSTANCE_LOGO,
    FileAsset.EntityTypeContext.INSTANCE_LOGIN_BACKGROUND,
}


class UploadError(Exception):
    def __init__(self, message: str, code: str, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


class UploadStorageError(UploadError):
    def __init__(self, message: str = "File storage is temporarily unavailable."):
        super().__init__(message, "upload_storage_unavailable", 503)


@dataclass(frozen=True)
class UploadMetadata:
    name: str
    size: int
    mime_type: str


def upload_error_payload(error: UploadError) -> dict:
    return {"error": error.message, "code": error.code, "status": False}


def _normalized_mime(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


def _mime_types_match(expected: str, actual: str) -> bool:
    expected = _normalized_mime(expected)
    actual = _normalized_mime(actual)
    if expected == actual:
        return True
    return any(expected in group and actual in group for group in MIME_EQUIVALENCE_GROUPS)


def _is_inline_image(entity_type: str | None) -> bool:
    return entity_type in INLINE_IMAGE_ENTITY_TYPES


def validate_upload_metadata(
    *,
    raw_name: object,
    raw_size: object,
    claimed_mime_type: object = None,
    entity_type: str | None = None,
) -> UploadMetadata:
    """Validate untrusted metadata and derive the authoritative MIME from the extension."""

    name = sanitize_filename(raw_name) if isinstance(raw_name, str) else None
    if not name or name in {".", ".."}:
        raise UploadError("A valid file name is required.", "invalid_file_name")

    try:
        size = int(raw_size)
    except (TypeError, ValueError):
        raise UploadError("A valid file size is required.", "invalid_file_size") from None

    if size < 1 or size > settings.FILE_SIZE_LIMIT:
        raise UploadError(
            f"File size must be between 1 and {settings.FILE_SIZE_LIMIT} bytes.",
            "invalid_file_size",
        )

    extension = PurePath(name).suffix.lower()
    policy = RASTER_IMAGE_MIME_BY_EXTENSION if _is_inline_image(entity_type) else ATTACHMENT_MIME_BY_EXTENSION
    mime_type = policy.get(extension)
    if not mime_type:
        raise UploadError("This file extension is not supported.", "unsupported_file_extension")

    claimed = _normalized_mime(claimed_mime_type if isinstance(claimed_mime_type, str) else None)
    if claimed and not _mime_types_match(mime_type, claimed):
        raise UploadError(
            "The file type does not match its extension.",
            "file_type_mismatch",
        )

    return UploadMetadata(name=name, size=size, mime_type=mime_type)


def build_pending_asset_key(*, namespace: str, name: str) -> str:
    safe_namespace = re.sub(r"[^A-Za-z0-9._-]", "-", namespace).strip(".-") or "assets"
    return f"{safe_namespace}/pending/{uuid.uuid4().hex}-{name}"


def build_server_asset_key(*, namespace: str, name: str) -> str:
    safe_namespace = re.sub(r"[^A-Za-z0-9._-]", "-", namespace).strip(".-") or "assets"
    return f"{safe_namespace}/assets/{uuid.uuid4().hex}-{name}"


def _build_final_asset_key(asset: FileAsset) -> str:
    current_key = str(asset.asset.name)
    if "/pending/" in current_key:
        prefix = current_key.split("/pending/", 1)[0]
    else:
        prefix = current_key.rsplit("/", 1)[0] if "/" in current_key else "assets"
    name = sanitize_filename(asset.attributes.get("name")) or "unnamed"
    return f"{prefix}/assets/{uuid.uuid4().hex}-{name}"


def _looks_like_text(content: bytes) -> bool:
    if b"\x00" in content:
        return False
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    if not decoded:
        return True
    control_count = sum(1 for char in decoded if ord(char) < 32 and char not in "\t\n\r\f")
    return control_count / len(decoded) <= 0.01


def validate_file_content(*, expected_mime: str, content: bytes) -> str:
    """Validate a bounded file prefix against the canonical type."""

    if not content:
        raise UploadError("The uploaded file is empty.", "empty_file", 422)

    try:
        detected_mime = _normalized_mime(magic.from_buffer(content, mime=True))
    except Exception as error:
        raise UploadStorageError("File validation is temporarily unavailable.") from error
    if expected_mime in TEXT_MIME_TYPES:
        if not _looks_like_text(content):
            raise UploadError(
                "The uploaded content does not match the expected text format.",
                "file_content_mismatch",
                422,
            )
        # libmagic commonly identifies JSON, CSV, Markdown, SVG and source files
        # as text/plain. The extension policy plus strict textual check is the
        # authoritative rule for download-only contexts.
        rejected_active_types = {"text/html", "application/xhtml+xml", "image/svg+xml"}
        if expected_mime == "image/svg+xml":
            accepted_detected_types = {
                "application/xml",
                "image/svg+xml",
                "text/plain",
                "text/xml",
            }
        elif expected_mime == "application/xml":
            accepted_detected_types = {"application/xml", "text/plain", "text/xml"}
        elif expected_mime == "text/javascript":
            accepted_detected_types = {
                "application/javascript",
                "text/javascript",
                "text/plain",
            }
        else:
            accepted_detected_types = {
                "application/json",
                "application/octet-stream",
                "inode/x-empty",
                "text/plain",
            }
            if detected_mime.startswith("text/") and detected_mime not in rejected_active_types:
                accepted_detected_types.add(detected_mime)

        if detected_mime and detected_mime not in accepted_detected_types:
            raise UploadError(
                "The uploaded content does not match the expected file type.",
                "file_content_mismatch",
                422,
            )
        return detected_mime or "text/plain"

    if not detected_mime or not _mime_types_match(expected_mime, detected_mime):
        raise UploadError(
            "The uploaded content does not match the expected file type.",
            "file_content_mismatch",
            422,
        )
    return detected_mime


def validate_multipart_upload(*, uploaded_file, entity_type: str | None) -> UploadMetadata:
    """Validate a Django multipart upload before its FileField writes to storage."""

    metadata = validate_upload_metadata(
        raw_name=getattr(uploaded_file, "name", None),
        raw_size=getattr(uploaded_file, "size", None),
        claimed_mime_type=getattr(uploaded_file, "content_type", None),
        entity_type=entity_type,
    )
    try:
        uploaded_file.seek(0)
        content = uploaded_file.read(min(metadata.size, UPLOAD_SIGNATURE_BYTES))
        validate_file_content(expected_mime=metadata.mime_type, content=content)
    except UploadError:
        raise
    except Exception as error:
        raise UploadError(
            "The uploaded file could not be inspected.",
            "file_validation_failed",
            422,
        ) from error
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    # The storage backend uses this value when persisting UploadedFile. Replace
    # the untrusted multipart header with the server-derived canonical type.
    uploaded_file.content_type = metadata.mime_type
    uploaded_file.name = metadata.name
    return metadata


def save_validated_multipart_asset(
    *,
    uploaded_file,
    metadata: UploadMetadata,
    storage,
    namespace,
    created_by_id,
    entity_type,
    entity_identifier,
    **relations,
) -> FileAsset:
    """Publish a validated server-received stream under an immutable key."""

    object_name = build_server_asset_key(namespace=str(namespace), name=metadata.name)
    try:
        uploaded_file.seek(0)
        uploaded = storage.upload_file(
            file_obj=uploaded_file,
            object_name=object_name,
            content_type=metadata.mime_type,
        )
        if not uploaded:
            raise UploadStorageError()

        object_metadata = storage.get_object_metadata(object_name)
        if (
            object_metadata is None
            or object_metadata.get("ContentLength") != metadata.size
            or not _mime_types_match(
                metadata.mime_type,
                object_metadata.get("ContentType"),
            )
        ):
            raise UploadStorageError()

        asset = FileAsset(
            asset=object_name,
            attributes={
                "name": metadata.name,
                "type": metadata.mime_type,
                "size": metadata.size,
            },
            size=metadata.size,
            entity_type=entity_type,
            entity_identifier=str(entity_identifier),
            is_uploaded=True,
            upload_validation_version=UPLOAD_VALIDATION_VERSION,
            storage_metadata={
                **object_metadata,
                "ValidatedAt": timezone.now().isoformat(),
                "ValidationVersion": UPLOAD_VALIDATION_VERSION,
            },
            **relations,
        )
        asset.save(created_by_id=created_by_id)
        return asset
    except Exception:
        # The key is server-generated and unique, so deletion is safe even if
        # the backend reported failure after partially persisting the object.
        storage.delete_files([object_name])
        raise


def revalidate_legacy_static_asset(*, asset_id, storage) -> FileAsset:
    """Validate and immutably republish a legacy public raster asset.

    Legacy metadata is not trusted. The canonical type is derived from the
    stored display name, checked against a bounded object prefix, and copied
    under a fresh key guarded by the source ETag before the database row is
    marked as validated.
    """

    copied_object_name = None
    source_object_name = None
    try:
        with transaction.atomic():
            asset = FileAsset.objects.select_for_update().get(id=asset_id)
            if asset.upload_validation_version == UPLOAD_VALIDATION_VERSION:
                return asset
            if (
                asset.upload_validation_version != 0
                or not asset.is_uploaded
                or asset.entity_type
                not in {
                    FileAsset.EntityTypeContext.USER_AVATAR,
                    FileAsset.EntityTypeContext.USER_COVER,
                    FileAsset.EntityTypeContext.WORKSPACE_LOGO,
                    FileAsset.EntityTypeContext.PROJECT_COVER,
                }
            ):
                raise UploadError(
                    "The legacy asset is not eligible for public revalidation.",
                    "legacy_asset_not_eligible",
                    422,
                )

            source_object_name = str(asset.asset.name)
            source_metadata = storage.get_object_metadata(source_object_name)
            source_size = (source_metadata or {}).get("ContentLength")
            source_etag = (source_metadata or {}).get("ETag")
            metadata = validate_upload_metadata(
                raw_name=(asset.attributes or {}).get("name"),
                raw_size=source_size,
                entity_type=asset.entity_type,
            )
            if not source_etag:
                raise UploadStorageError()

            content = storage.get_object_prefix(
                source_object_name,
                min(metadata.size, UPLOAD_SIGNATURE_BYTES),
                source_etag,
            )
            if content is None:
                raise UploadStorageError()
            detected_mime = validate_file_content(
                expected_mime=metadata.mime_type,
                content=content,
            )

            copied_object_name = _build_final_asset_key(asset)
            if (
                storage.copy_object(
                    source_object_name,
                    copied_object_name,
                    source_etag=source_etag,
                    content_type=metadata.mime_type,
                )
                is None
            ):
                raise UploadStorageError()
            final_metadata = storage.get_object_metadata(copied_object_name)
            if (
                final_metadata is None
                or final_metadata.get("ContentLength") != metadata.size
                or not _mime_types_match(
                    metadata.mime_type,
                    final_metadata.get("ContentType"),
                )
            ):
                raise UploadStorageError()

            asset.asset.name = copied_object_name
            asset.attributes = {
                **(asset.attributes or {}),
                "name": metadata.name,
                "type": metadata.mime_type,
                "size": metadata.size,
            }
            asset.size = metadata.size
            asset.upload_validation_version = UPLOAD_VALIDATION_VERSION
            asset.storage_metadata = {
                **final_metadata,
                "DetectedContentType": detected_mime,
                "ValidatedAt": timezone.now().isoformat(),
                "ValidationVersion": UPLOAD_VALIDATION_VERSION,
                "ValidationSource": "legacy-static-revalidation",
            }
            asset.save(
                update_fields=[
                    "asset",
                    "attributes",
                    "size",
                    "upload_validation_version",
                    "storage_metadata",
                    "updated_at",
                ]
            )
            if not FileAsset.all_objects.exclude(id=asset.id).filter(asset=source_object_name).exists():
                from plane.bgtasks.file_asset_task import delete_superseded_asset

                transaction.on_commit(
                    lambda: delete_superseded_asset.apply_async(
                        args=[source_object_name, str(asset.id)],
                        countdown=storage.signed_url_expiration + 60,
                    )
                )
            return asset
    except UploadError as error:
        if copied_object_name:
            storage.delete_files([copied_object_name])
        if not isinstance(error, UploadStorageError):
            quarantined = FileAsset.objects.filter(
                id=asset_id,
                upload_validation_version=0,
            ).update(upload_validation_version=UPLOAD_VALIDATION_REJECTED)
            if (
                quarantined
                and source_object_name
                and not FileAsset.all_objects.exclude(id=asset_id).filter(asset=source_object_name).exists()
            ):
                from plane.bgtasks.file_asset_task import delete_superseded_asset

                transaction.on_commit(
                    lambda: delete_superseded_asset.apply_async(
                        args=[source_object_name, str(asset_id)],
                        countdown=storage.signed_url_expiration + 60,
                    )
                )
        raise
    except Exception:
        if copied_object_name:
            storage.delete_files([copied_object_name])
        raise


def complete_asset_upload(*, asset_id, storage) -> tuple[FileAsset, bool, str | None]:
    """Validate and atomically promote a pending object.

    Returns the refreshed asset, whether it was newly completed, and the old
    staging key which should be deleted after the presigned upload expires.
    """

    pending_key = None
    final_key = None
    try:
        with transaction.atomic():
            asset = FileAsset.objects.select_for_update().get(id=asset_id, is_deleted=False)
            if asset.is_uploaded:
                return asset, False, None

            pending_key = str(asset.asset.name)
            expected_mime = _normalized_mime(asset.attributes.get("type"))
            expected_size = int(asset.size)
            metadata = storage.get_object_metadata(pending_key)
            if metadata is None:
                raise UploadStorageError()

            actual_size = metadata.get("ContentLength")
            actual_type = _normalized_mime(metadata.get("ContentType"))
            etag = metadata.get("ETag")
            if actual_size != expected_size:
                raise UploadError(
                    "The uploaded file size does not match the declared size.",
                    "file_size_mismatch",
                    422,
                )
            if not etag:
                raise UploadStorageError()
            if not _mime_types_match(expected_mime, actual_type):
                raise UploadError(
                    "The uploaded Content-Type does not match the accepted type.",
                    "file_type_mismatch",
                    422,
                )

            content = storage.get_object_prefix(
                pending_key,
                byte_count=min(expected_size, UPLOAD_SIGNATURE_BYTES),
                etag=etag,
            )
            if content is None:
                raise UploadStorageError()
            detected_mime = validate_file_content(expected_mime=expected_mime, content=content)

            final_key = _build_final_asset_key(asset)
            copied = storage.copy_object(
                pending_key,
                final_key,
                source_etag=etag,
                content_type=expected_mime,
            )
            if copied is None:
                raise UploadStorageError()

            final_metadata = storage.get_object_metadata(final_key)
            if final_metadata is None or final_metadata.get("ContentLength") != expected_size:
                storage.delete_files([final_key])
                raise UploadStorageError()

            asset.asset.name = final_key
            asset.storage_metadata = {
                **final_metadata,
                "DetectedContentType": detected_mime,
                "ValidatedAt": timezone.now().isoformat(),
                "ValidationVersion": UPLOAD_VALIDATION_VERSION,
            }
            asset.is_uploaded = True
            asset.upload_validation_version = UPLOAD_VALIDATION_VERSION
            asset.save(
                update_fields=[
                    "asset",
                    "storage_metadata",
                    "is_uploaded",
                    "upload_validation_version",
                    "updated_at",
                ]
            )
            from plane.bgtasks.file_asset_task import delete_staging_asset

            delete_staging_asset.apply_async(
                args=[pending_key],
                countdown=UPLOAD_URL_EXPIRATION_SECONDS + 60,
            )
            return asset, True, pending_key
    except UploadError as error:
        if pending_key and not isinstance(error, UploadStorageError):
            storage.delete_files([pending_key])
            from plane.bgtasks.file_asset_task import delete_staging_asset

            delete_staging_asset.apply_async(
                args=[pending_key],
                countdown=UPLOAD_URL_EXPIRATION_SECONDS + 60,
            )
            FileAsset.objects.filter(id=asset_id, is_uploaded=False).update(
                is_deleted=True,
                deleted_at=timezone.now(),
            )
            logger.warning(
                "Rejected file upload",
                extra={"asset_id": str(asset_id), "reason": error.code},
            )
        raise
    except Exception:
        if final_key:
            storage.delete_files([final_key])
        raise
