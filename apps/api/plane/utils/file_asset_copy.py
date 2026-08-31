# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Copy a stored file into a second asset row.

Extracted from ``DuplicateAssetEndpoint`` so the duplicate-asset API and project
duplication share one implementation of the validation sequence. Getting any
step wrong here means either a broken object in storage or an asset row that
claims a size and type the stored bytes do not have, so there should only ever
be one copy of this logic.

The caller is responsible for authorizing the read of ``original_asset``; this
function re-checks what it can (upload state, validation version, and the
per-entity read rule) but does not know who is asking beyond ``actor_id``.
"""

import uuid

from django.utils import timezone

from plane.db.models import FileAsset
from plane.utils.file_asset_permissions import can_read_file_asset
from plane.utils.file_asset_upload import (
    UPLOAD_VALIDATION_VERSION,
    UploadError,
    validate_upload_metadata,
)
from plane.utils.path_validator import sanitize_filename


class AssetCopyError(Exception):
    """A copy that could not be completed, carrying the status the API reports."""

    def __init__(self, code: str, status_code: int, payload: dict | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.payload = payload or {"error": code}


def copyable_asset(*, asset_id, workspace, actor_id) -> FileAsset | None:
    """The source row, or None when it is missing, unvalidated or unreadable.

    Deliberately collapses "does not exist" and "you may not read it" into one
    result: telling them apart would confirm the existence of an asset the
    caller cannot see.
    """
    original = FileAsset.objects.filter(
        id=asset_id,
        is_uploaded=True,
        workspace=workspace,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    ).first()

    if not original:
        return None
    if not can_read_file_asset(user_id=actor_id, asset=original):
        return None
    return original


def duplicate_file_asset(*, storage, original_asset, workspace, entity_type, entity_fields, project_id, actor_id):
    """Server-side copy the stored object and create a matching asset row.

    Raises :class:`AssetCopyError` rather than returning a response, so both an
    HTTP view and a background caller can decide what to do.
    """
    try:
        metadata = validate_upload_metadata(
            raw_name=(original_asset.attributes or {}).get("name"),
            raw_size=original_asset.size,
            claimed_mime_type=(original_asset.attributes or {}).get("type"),
            entity_type=entity_type,
        )
    except UploadError as error:
        from plane.utils.file_asset_upload import upload_error_payload

        raise AssetCopyError("upload_invalid", error.http_status, upload_error_payload(error)) from error

    source_metadata = storage.get_object_metadata(original_asset.asset.name)
    source_etag = (source_metadata or {}).get("ETag")
    if not source_etag:
        raise AssetCopyError("storage_unavailable", 503, {"error": "File storage is temporarily unavailable."})

    sanitized_name = sanitize_filename(metadata.name) or "unnamed"
    destination_key = f"{workspace.id}/{uuid.uuid4().hex}-{sanitized_name}"
    copied = storage.copy_object(
        original_asset.asset.name,
        destination_key,
        source_etag=source_etag,
        content_type=metadata.mime_type,
    )

    # Verify the bytes that landed rather than trusting the copy call, and take
    # the orphan back out of storage when they do not match.
    final_metadata = storage.get_object_metadata(destination_key) if copied else None
    final_type = ((final_metadata or {}).get("ContentType") or "").split(";", 1)[0].strip().lower()
    if (
        final_metadata is None
        or final_metadata.get("ContentLength") != metadata.size
        or final_type != metadata.mime_type
    ):
        storage.delete_files([destination_key])
        raise AssetCopyError("storage_unavailable", 503, {"error": "File storage is temporarily unavailable."})

    create_fields = {"workspace_id": workspace.id, "project_id": project_id, **entity_fields}
    try:
        return FileAsset.objects.create(
            attributes={"name": metadata.name, "type": metadata.mime_type, "size": metadata.size},
            asset=destination_key,
            size=metadata.size,
            created_by_id=actor_id,
            entity_type=entity_type,
            storage_metadata={
                **final_metadata,
                "DetectedContentType": (original_asset.storage_metadata or {}).get(
                    "DetectedContentType", metadata.mime_type
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
