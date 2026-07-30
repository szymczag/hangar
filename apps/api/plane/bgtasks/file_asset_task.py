# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import timedelta

# Django imports
from django.utils import timezone
from django.db.models import Q

# Third party imports
from celery import shared_task

# Module imports
from plane.db.models import FileAsset
from plane.settings.storage import S3Storage


@shared_task
def delete_staging_asset(object_name):
    """Delete a staging key after its presigned upload credentials expire."""
    if not isinstance(object_name, str) or "/pending/" not in object_name:
        return
    S3Storage().delete_files([object_name])


@shared_task
def delete_unuploaded_file_asset():
    """Delete stale database rows and their pending object-storage keys."""
    cutoff = timezone.now() - timedelta(hours=int(os.environ.get("UNUPLOADED_ASSET_DELETE_HOURS", "1")))
    stale_assets = FileAsset.objects.filter(Q(created_at__lt=cutoff) & Q(is_uploaded=False))
    object_names = [
        str(name) for name in stale_assets.values_list("asset", flat=True) if name and "/pending/" in str(name)
    ]
    if object_names:
        S3Storage().delete_files(object_names)
    stale_assets.delete()
