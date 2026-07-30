# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import timedelta

# Django imports
from django.utils import timezone
from django.db.models import Q
from django.core.cache import cache

# Third party imports
from celery import shared_task

# Module imports
from plane.db.models import FileAsset
from plane.settings.storage import S3Storage
from plane.utils.file_asset_upload import (
    UPLOAD_VALIDATION_REJECTED,
    UPLOAD_VALIDATION_VERSION,
    UploadError,
    UploadStorageError,
    revalidate_legacy_static_asset,
)


LEGACY_REVALIDATION_CACHE_TTL = 15 * 60


class AssetObjectCleanupError(Exception):
    pass


def legacy_revalidation_cache_key(asset_id) -> str:
    return f"legacy-static-asset-revalidation:{asset_id}"


def enqueue_legacy_static_revalidation(asset_id) -> bool:
    """Publish at most one legacy revalidation task per asset and TTL window."""

    cache_key = legacy_revalidation_cache_key(asset_id)
    if not cache.add(cache_key, "1", LEGACY_REVALIDATION_CACHE_TTL):
        return False
    try:
        revalidate_legacy_static_asset_task.apply_async(args=[str(asset_id)])
    except Exception:
        cache.delete(cache_key)
        raise
    return True


@shared_task(
    autoretry_for=(AssetObjectCleanupError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def delete_staging_asset(object_name):
    """Delete a staging key after its presigned upload credentials expire."""
    if not isinstance(object_name, str) or "/pending/" not in object_name:
        return
    if not S3Storage().delete_files([object_name]):
        raise AssetObjectCleanupError("Could not delete staging asset")


@shared_task(
    autoretry_for=(AssetObjectCleanupError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def delete_superseded_asset(object_name, asset_id):
    """Delete one explicit legacy key after rechecking its trusted DB state."""

    if not isinstance(object_name, str) or not object_name or len(object_name) > 800:
        return
    asset = (
        FileAsset.all_objects.filter(id=asset_id)
        .only(
            "asset",
            "upload_validation_version",
        )
        .first()
    )
    if asset and asset.upload_validation_version not in {
        UPLOAD_VALIDATION_REJECTED,
        UPLOAD_VALIDATION_VERSION,
    }:
        return
    if FileAsset.all_objects.exclude(id=asset_id).filter(asset=object_name).exists():
        return
    if asset and str(asset.asset.name) == object_name and asset.upload_validation_version != UPLOAD_VALIDATION_REJECTED:
        return
    if not S3Storage().delete_files([object_name]):
        raise AssetObjectCleanupError("Could not delete superseded asset")


@shared_task(bind=True, max_retries=5)
def revalidate_legacy_static_asset_task(self, asset_id):
    """Validate a legacy public raster outside the anonymous request path."""

    cache_key = legacy_revalidation_cache_key(asset_id)
    try:
        revalidate_legacy_static_asset(
            asset_id=asset_id,
            storage=S3Storage(),
        )
    except UploadStorageError as error:
        raise self.retry(
            exc=error,
            countdown=min(2 ** (self.request.retries + 1), 300),
        ) from error
    except (UploadError, FileAsset.DoesNotExist):
        cache.delete(cache_key)
        return
    cache.delete(cache_key)


@shared_task(soft_time_limit=20, time_limit=25)
def download_oauth_avatar(*, avatar_url, user_id, provider):
    """Mirror an untrusted remote avatar under a hard worker time budget."""

    if (
        not isinstance(avatar_url, str)
        or not avatar_url
        or len(avatar_url) > 2048
        or not isinstance(provider, str)
        or not provider
        or len(provider) > 64
    ):
        return

    from plane.authentication.adapter.base import Adapter
    from plane.db.models import User

    user = User.objects.filter(id=user_id, avatar=avatar_url).first()
    if user is None:
        return
    file_asset = Adapter(request=None, provider=provider).download_and_upload_avatar(
        avatar_url=avatar_url,
        user=user,
    )
    if file_asset is None:
        return

    # Do not overwrite a newer avatar choice made while the task was running.
    updated = User.objects.filter(
        id=user_id,
        avatar=avatar_url,
        avatar_asset__isnull=True,
    ).update(
        avatar="",
        avatar_asset=file_asset,
    )
    if not updated and S3Storage().delete_files([file_asset.asset.name]):
        file_asset.delete(soft=False)


@shared_task(
    autoretry_for=(AssetObjectCleanupError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def delete_unuploaded_file_asset():
    """Delete stale database rows and their pending object-storage keys."""
    cutoff = timezone.now() - timedelta(hours=int(os.environ.get("UNUPLOADED_ASSET_DELETE_HOURS", "1")))
    stale_assets = FileAsset.all_objects.filter(
        Q(created_at__lt=cutoff) & Q(is_uploaded=False),
        asset__contains="/pending/",
    )
    asset_rows = [(asset_id, str(name)) for asset_id, name in stale_assets.values_list("id", "asset") if name]
    if not asset_rows:
        return

    storage = S3Storage()
    # S3 DeleteObjects accepts at most 1,000 keys. Keep each batch's database
    # references unless storage confirms the full batch; confirmed earlier
    # batches may be safely removed even if a later batch needs a retry.
    for index in range(0, len(asset_rows), 1000):
        batch = asset_rows[index : index + 1000]
        if not storage.delete_files([name for _, name in batch]):
            raise AssetObjectCleanupError("Could not delete stale pending assets")
        FileAsset.all_objects.filter(id__in=[asset_id for asset_id, _ in batch]).delete()
