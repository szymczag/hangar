# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from io import BytesIO
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.test import override_settings

from plane.db.models import FileAsset
from plane.settings.storage import S3Storage
from plane.utils.file_asset_upload import (
    UploadError,
    build_pending_asset_key,
    complete_asset_upload,
    validate_file_content,
    validate_upload_metadata,
)


@pytest.mark.unit
@override_settings(FILE_SIZE_LIMIT=1024)
def test_text_file_metadata_is_derived_from_extension_not_client_mime():
    metadata = validate_upload_metadata(
        raw_name="notes.txt",
        raw_size="12",
        claimed_mime_type="text/plain",
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
    )

    assert metadata.name == "notes.txt"
    assert metadata.size == 12
    assert metadata.mime_type == "text/plain"


@pytest.mark.unit
@override_settings(FILE_SIZE_LIMIT=1024)
@pytest.mark.parametrize("size", [0, -1, 1025, "invalid", None])
def test_upload_metadata_rejects_invalid_sizes(size):
    with pytest.raises(UploadError) as error:
        validate_upload_metadata(
            raw_name="notes.txt",
            raw_size=size,
            claimed_mime_type="text/plain",
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        )

    assert error.value.code == "invalid_file_size"


@pytest.mark.unit
@override_settings(FILE_SIZE_LIMIT=1024)
def test_inline_assets_reject_svg():
    with pytest.raises(UploadError) as error:
        validate_upload_metadata(
            raw_name="avatar.svg",
            raw_size=100,
            claimed_mime_type="image/svg+xml",
            entity_type=FileAsset.EntityTypeContext.USER_AVATAR,
        )

    assert error.value.code == "unsupported_file_extension"


@pytest.mark.unit
@override_settings(FILE_SIZE_LIMIT=1024)
def test_claimed_type_must_match_extension():
    with pytest.raises(UploadError) as error:
        validate_upload_metadata(
            raw_name="payload.png",
            raw_size=100,
            claimed_mime_type="text/html",
            entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
        )

    assert error.value.code == "file_type_mismatch"


@pytest.mark.unit
def test_pending_key_uses_server_namespace_and_marker():
    key = build_pending_asset_key(namespace="../../workspace id", name="report.pdf")

    assert key.startswith("workspace-id/pending/")
    assert key.endswith("-report.pdf")
    assert ".." not in key


@pytest.mark.unit
@patch("plane.utils.file_asset_upload.magic.from_buffer", return_value="text/plain")
def test_signatureless_text_is_accepted_after_text_validation(_from_buffer):
    assert validate_file_content(expected_mime="text/csv", content=b"name,value\nsafe,1\n") == "text/plain"


@pytest.mark.unit
@patch("plane.utils.file_asset_upload.magic.from_buffer", return_value="application/x-dosexec")
def test_executable_bytes_are_rejected_for_image(_from_buffer):
    with pytest.raises(UploadError) as error:
        validate_file_content(expected_mime="image/png", content=b"MZ" + b"\0" * 128)

    assert error.value.code == "file_content_mismatch"


class _Body(BytesIO):
    closed_by_storage = False

    def close(self):
        self.closed_by_storage = True
        super().close()


@pytest.mark.unit
def test_storage_prefix_read_is_bounded_and_etag_bound():
    storage = object.__new__(S3Storage)
    storage.aws_storage_bucket_name = "bucket"
    body = _Body(b"0123456789")
    storage.s3_client = Mock()
    storage.s3_client.get_object.return_value = {"Body": body}

    result = storage.get_object_prefix("pending/key", byte_count=4, etag='"etag"')

    assert result == b"0123"
    assert body.closed_by_storage
    storage.s3_client.get_object.assert_called_once_with(
        Bucket="bucket",
        Key="pending/key",
        Range="bytes=0-3",
        IfMatch='"etag"',
    )


@pytest.mark.unit
def test_storage_promotion_is_etag_bound_and_replaces_content_type():
    storage = object.__new__(S3Storage)
    storage.aws_storage_bucket_name = "bucket"
    storage.s3_client = Mock()
    storage.s3_client.copy_object.return_value = {"CopyObjectResult": {"ETag": '"etag"'}}

    result = storage.copy_object(
        "workspace/pending/key",
        "workspace/assets/key",
        source_etag='"etag"',
        content_type="application/pdf",
    )

    assert result is not None
    storage.s3_client.copy_object.assert_called_once_with(
        Bucket="bucket",
        CopySource={"Bucket": "bucket", "Key": "workspace/pending/key"},
        Key="workspace/assets/key",
        CopySourceIfMatch='"etag"',
        ContentType="application/pdf",
        MetadataDirective="REPLACE",
    )


class _FakePromotionStorage:
    def __init__(self, *, content_type, content, size):
        self.content_type = content_type
        self.content = content
        self.size = size
        self.deleted = []
        self.copies = []
        self.metadata_calls = 0

    def get_object_metadata(self, _key):
        self.metadata_calls += 1
        return {
            "ContentType": self.content_type,
            "ContentLength": self.size,
            "ETag": '"final"' if self.metadata_calls > 1 else '"pending"',
        }

    def get_object_prefix(self, _key, *, byte_count, etag):
        assert etag == '"pending"'
        return self.content[:byte_count]

    def copy_object(self, source, destination, *, source_etag, content_type):
        self.copies.append((source, destination, source_etag, content_type))
        return {"CopyObjectResult": {"ETag": '"final"'}}

    def delete_files(self, keys):
        self.deleted.extend(keys)
        return True


@pytest.mark.django_db
@patch("plane.bgtasks.file_asset_task.delete_staging_asset.apply_async")
@patch("plane.utils.file_asset_upload.magic.from_buffer", return_value="application/pdf")
def test_completion_promotes_validated_etag_and_is_idempotent(
    _from_buffer,
    cleanup_task,
    django_user_model,
):
    from plane.db.models import Workspace

    user = django_user_model.objects.create(email="uploader@example.test")
    workspace = Workspace.objects.create(name="Upload Test", slug="upload-test", owner=user)
    asset = FileAsset(
        attributes={"name": "report.pdf", "type": "application/pdf", "size": 9},
        asset=f"{workspace.id}/pending/report.pdf",
        size=9,
        workspace=workspace,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
    )
    asset.save(created_by_id=user.id)
    storage = _FakePromotionStorage(
        content_type="application/pdf",
        content=b"%PDF-1.7\n",
        size=9,
    )

    completed_asset, completed, pending_key = complete_asset_upload(
        asset_id=asset.id,
        storage=storage,
    )
    repeated_asset, repeated, repeated_pending = complete_asset_upload(
        asset_id=asset.id,
        storage=storage,
    )

    assert completed is True
    assert repeated is False
    assert pending_key.endswith("/pending/report.pdf")
    assert repeated_pending is None
    assert completed_asset.is_uploaded is True
    assert repeated_asset.asset.name == completed_asset.asset.name
    assert "/assets/" in completed_asset.asset.name
    assert len(storage.copies) == 1
    cleanup_task.assert_called_once()


@pytest.mark.django_db
@patch("plane.bgtasks.file_asset_task.delete_staging_asset.apply_async")
@patch("plane.utils.file_asset_upload.magic.from_buffer", return_value="application/x-dosexec")
def test_completion_rejects_spoofed_image_and_deletes_pending_object(
    _from_buffer,
    cleanup_task,
    django_user_model,
):
    from plane.db.models import Workspace

    user = django_user_model.objects.create(email="spoof@example.test")
    workspace = Workspace.objects.create(name="Spoof Test", slug="spoof-test", owner=user)
    pending_key = f"{workspace.id}/pending/payload.png"
    asset = FileAsset(
        attributes={"name": "payload.png", "type": "image/png", "size": 130},
        asset=pending_key,
        size=130,
        workspace=workspace,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
    )
    asset.save(created_by_id=user.id)
    storage = _FakePromotionStorage(
        content_type="image/png",
        content=b"MZ" + b"\0" * 128,
        size=130,
    )

    with pytest.raises(UploadError) as error:
        complete_asset_upload(asset_id=asset.id, storage=storage)

    rejected = FileAsset.all_objects.get(id=asset.id)
    assert error.value.code == "file_content_mismatch"
    assert rejected.is_deleted is True
    assert pending_key in storage.deleted
    cleanup_task.assert_called_once()


@pytest.mark.django_db
@pytest.mark.smoke
@patch("plane.bgtasks.file_asset_task.delete_staging_asset.apply_async")
def test_real_s3_text_upload_is_validated_and_promoted(_cleanup_task, django_user_model):
    from plane.db.models import Workspace

    suffix = uuid4().hex[:10]
    user = django_user_model.objects.create(email=f"minio-{suffix}@example.test")
    workspace = Workspace.objects.create(
        name="MinIO Upload Test",
        slug=f"minio-upload-{suffix}",
        owner=user,
    )
    content = b"safe text attachment\n"
    pending_key = f"{workspace.id}/pending/{suffix}-notes.txt"
    asset = FileAsset(
        attributes={"name": "notes.txt", "type": "text/plain", "size": len(content)},
        asset=pending_key,
        size=len(content),
        workspace=workspace,
        entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT,
    )
    asset.save(created_by_id=user.id)

    storage = S3Storage()
    storage.s3_client.put_object(
        Bucket=storage.aws_storage_bucket_name,
        Key=pending_key,
        Body=content,
        ContentType="text/plain",
    )
    final_key = None
    try:
        completed_asset, completed, _ = complete_asset_upload(
            asset_id=asset.id,
            storage=storage,
        )
        final_key = completed_asset.asset.name
        stored = storage.s3_client.get_object(
            Bucket=storage.aws_storage_bucket_name,
            Key=final_key,
        )

        assert completed is True
        try:
            assert stored["Body"].read() == content
        finally:
            stored["Body"].close()
        assert stored["ContentType"] == "text/plain"
        assert completed_asset.storage_metadata["DetectedContentType"] == "text/plain"
    finally:
        storage.delete_files([key for key in [pending_key, final_key] if key])
