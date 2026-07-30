# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest import mock

import pytest
from django.core.cache import cache

from plane.db.models import FileAsset
from plane.utils.file_asset_upload import (
    UploadError,
    UPLOAD_VALIDATION_REJECTED,
    revalidate_legacy_static_asset,
)
from plane.bgtasks.file_asset_task import (
    delete_superseded_asset,
    enqueue_legacy_static_revalidation,
    legacy_revalidation_cache_key,
)


@pytest.mark.django_db
@mock.patch(
    "plane.utils.file_asset_upload.magic.from_buffer",
    return_value="text/html",
)
def test_legacy_static_revalidation_rejects_spoof_without_copying(
    _magic,
    workspace,
    create_user,
):
    asset = FileAsset.objects.create(
        attributes={"name": "logo.png", "type": "image/png", "size": 32},
        asset=f"{workspace.id}/logo.png",
        size=32,
        workspace=workspace,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.WORKSPACE_LOGO,
        is_uploaded=True,
    )
    storage = mock.Mock()
    storage.get_object_metadata.return_value = {
        "ContentType": "image/png",
        "ContentLength": 32,
        "ETag": '"source-etag"',
    }
    storage.get_object_prefix.return_value = b"<html><script>alert(1)</script>"

    with pytest.raises(UploadError) as error:
        revalidate_legacy_static_asset(asset_id=asset.id, storage=storage)

    assert error.value.code == "file_content_mismatch"
    storage.copy_object.assert_not_called()
    asset.refresh_from_db()
    assert asset.storage_metadata == {}
    assert asset.upload_validation_version == UPLOAD_VALIDATION_REJECTED


@pytest.mark.django_db
@mock.patch(
    "plane.utils.file_asset_upload.magic.from_buffer",
    return_value="image/png",
)
def test_legacy_static_revalidation_deletes_copy_when_final_metadata_mismatches(
    _magic,
    workspace,
    create_user,
):
    asset = FileAsset.objects.create(
        attributes={"name": "logo.png", "type": "image/png", "size": 16},
        asset=f"{workspace.id}/logo.png",
        size=16,
        workspace=workspace,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.WORKSPACE_LOGO,
        is_uploaded=True,
    )
    storage = mock.Mock()
    storage.get_object_metadata.side_effect = [
        {
            "ContentType": "image/png",
            "ContentLength": 16,
            "ETag": '"source-etag"',
        },
        {
            "ContentType": "image/png",
            "ContentLength": 15,
            "ETag": '"copied-etag"',
        },
    ]
    storage.get_object_prefix.return_value = b"\x89PNG\r\n\x1a\ncontent"
    storage.copy_object.return_value = {"CopyObjectResult": {}}

    with pytest.raises(UploadError) as error:
        revalidate_legacy_static_asset(asset_id=asset.id, storage=storage)

    assert error.value.code == "upload_storage_unavailable"
    storage.delete_files.assert_called_once()
    asset.refresh_from_db()
    assert asset.asset.name == f"{workspace.id}/logo.png"
    assert asset.storage_metadata == {}


@pytest.mark.django_db
def test_legacy_revalidation_enqueue_is_deduplicated(workspace, create_user):
    asset = FileAsset.objects.create(
        attributes={"name": "logo.png", "type": "image/png", "size": 16},
        asset=f"{workspace.id}/logo.png",
        size=16,
        workspace=workspace,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.WORKSPACE_LOGO,
        is_uploaded=True,
    )
    cache.delete(legacy_revalidation_cache_key(asset.id))

    with mock.patch("plane.bgtasks.file_asset_task.revalidate_legacy_static_asset_task.apply_async") as apply_async:
        assert enqueue_legacy_static_revalidation(asset.id) is True
        assert enqueue_legacy_static_revalidation(asset.id) is False

    apply_async.assert_called_once_with(args=[str(asset.id)])


@pytest.mark.django_db
def test_superseded_asset_task_deletes_only_after_reference_recheck(
    workspace,
    create_user,
):
    old_key = f"{workspace.id}/legacy-logo.png"
    asset = FileAsset.objects.create(
        attributes={"name": "logo.png", "type": "image/png", "size": 16},
        asset=old_key,
        size=16,
        workspace=workspace,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.WORKSPACE_LOGO,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_REJECTED,
    )

    with mock.patch("plane.bgtasks.file_asset_task.S3Storage") as storage_class:
        storage_class.return_value.delete_files.return_value = True
        delete_superseded_asset.run(old_key, str(asset.id))

    storage_class.return_value.delete_files.assert_called_once_with([old_key])
