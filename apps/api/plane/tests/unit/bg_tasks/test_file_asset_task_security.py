# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import timedelta
from unittest import mock
from uuid import uuid4

import pytest
from django.utils import timezone

from plane.bgtasks.file_asset_task import (
    delete_unuploaded_file_asset,
    download_oauth_avatar,
)
from plane.db.models import FileAsset
from plane.utils.file_asset_upload import UPLOAD_VALIDATION_VERSION


@pytest.mark.unit
@pytest.mark.django_db
def test_pending_cleanup_includes_soft_deleted_rows(
    workspace,
    create_user,
):
    asset = FileAsset.objects.create(
        attributes={"name": "pending.png", "type": "image/png", "size": 24},
        asset=f"{workspace.id}/pending/{uuid4().hex}-pending.png",
        size=24,
        workspace=workspace,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.WORKSPACE_LOGO,
        is_uploaded=False,
    )
    FileAsset.all_objects.filter(id=asset.id).update(
        created_at=timezone.now() - timedelta(hours=2),
        deleted_at=timezone.now(),
    )

    with mock.patch("plane.bgtasks.file_asset_task.S3Storage") as storage_class:
        storage_class.return_value.delete_files.return_value = True
        delete_unuploaded_file_asset.run()

    storage_class.return_value.delete_files.assert_called_once_with([asset.asset.name])
    assert not FileAsset.all_objects.filter(id=asset.id).exists()


@pytest.mark.unit
@pytest.mark.django_db
def test_oauth_avatar_worker_publishes_only_if_remote_url_is_still_current(
    create_user,
):
    avatar_url = "https://cdn.example.com/avatar.png"
    create_user.avatar = avatar_url
    create_user.save(update_fields=["avatar"])
    asset = FileAsset.objects.create(
        attributes={"name": "avatar.png", "type": "image/png", "size": 24},
        asset=f"{uuid4().hex}-avatar.png",
        size=24,
        user=create_user,
        created_by=create_user,
        entity_type=FileAsset.EntityTypeContext.USER_AVATAR,
        is_uploaded=True,
        upload_validation_version=UPLOAD_VALIDATION_VERSION,
    )

    with mock.patch(
        "plane.authentication.adapter.base.Adapter.download_and_upload_avatar",
        return_value=asset,
    ):
        download_oauth_avatar.run(
            avatar_url=avatar_url,
            user_id=str(create_user.id),
            provider="gitea",
        )

    create_user.refresh_from_db()
    assert create_user.avatar == ""
    assert create_user.avatar_asset_id == asset.id
    assert download_oauth_avatar.soft_time_limit == 20
    assert download_oauth_avatar.time_limit == 25
