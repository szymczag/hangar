# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.core.management.base import BaseCommand

from plane.db.models import FileAsset
from plane.settings.storage import S3Storage
from plane.utils.file_asset_upload import (
    UploadError,
    UploadStorageError,
    revalidate_legacy_static_asset,
)


class Command(BaseCommand):
    help = "Validate and immutably republish legacy public raster assets."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of legacy assets to inspect.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit is not None and limit < 1:
            self.stderr.write(self.style.ERROR("--limit must be greater than zero."))
            return

        eligible_types = [
            FileAsset.EntityTypeContext.USER_AVATAR,
            FileAsset.EntityTypeContext.USER_COVER,
            FileAsset.EntityTypeContext.WORKSPACE_LOGO,
            FileAsset.EntityTypeContext.PROJECT_COVER,
        ]
        queryset = (
            FileAsset.objects.filter(
                is_uploaded=True,
                entity_type__in=eligible_types,
                upload_validation_version=0,
            )
            .order_by("created_at", "id")
            .values_list("id", flat=True)
        )
        if limit is not None:
            queryset = queryset[:limit]

        storage = S3Storage(is_server=True)
        validated = 0
        quarantined = 0
        retryable = 0
        for asset_id in queryset.iterator():
            try:
                revalidate_legacy_static_asset(
                    asset_id=asset_id,
                    storage=storage,
                )
            except UploadStorageError as error:
                retryable += 1
                self.stderr.write(f"{asset_id}: retryable failure ({error.code})")
            except UploadError as error:
                quarantined += 1
                self.stderr.write(f"{asset_id}: quarantined ({error.code})")
            else:
                validated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Validated {validated} legacy assets; quarantined {quarantined}; "
                f"retryable failures {retryable}."
            )
        )
