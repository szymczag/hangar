# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from io import BytesIO
import logging

from plane.settings.storage import S3Storage


logger = logging.getLogger(__name__)


def upload_import_source(content: bytes, object_name: str) -> bool:
    try:
        return S3Storage().upload_file(BytesIO(content), object_name, content_type="text/csv")
    except Exception as exc:  # noqa: BLE001 - storage errors must not leak request details
        logger.error("Import source upload failed with %s", type(exc).__name__)
        return False


def read_import_source(object_name: str) -> bytes:
    storage = S3Storage()
    response = storage.s3_client.get_object(Bucket=storage.aws_storage_bucket_name, Key=object_name)
    return response["Body"].read()


def delete_import_source(object_name: str) -> bool:
    if not object_name:
        return True
    try:
        return S3Storage().delete_files([object_name])
    except Exception as exc:  # noqa: BLE001 - cleanup must remain best-effort
        logger.error("Import source cleanup failed with %s", type(exc).__name__)
        return False
