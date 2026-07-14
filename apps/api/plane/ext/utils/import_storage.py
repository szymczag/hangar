# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from io import BytesIO
import logging
import os

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)

_ANONYMOUS_DENIAL_CODES = {
    "401",
    "403",
    "404",
    "AccessDenied",
    "AllAccessDisabled",
    "InvalidAccessKeyId",
    "NoSuchKey",
    "NotFound",
    "SignatureDoesNotMatch",
}


class ImportStorageConfigurationError(RuntimeError):
    pass


class ImportSourceStorage:
    """Private object storage used only for short-lived import source files."""

    def __init__(self) -> None:
        main_bucket = os.environ.get("AWS_S3_BUCKET_NAME", "uploads").strip()
        self.bucket_name = os.environ.get("IMPORT_S3_BUCKET_NAME", f"{main_bucket}-imports").strip()
        if not self.bucket_name or self.bucket_name == main_bucket:
            raise ImportStorageConfigurationError("The import bucket must be configured separately.")

        endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL") or os.environ.get("MINIO_ENDPOINT_URL")
        addressing_style = "path" if os.environ.get("USE_MINIO") == "1" else "auto"
        base_config = {"s3": {"addressing_style": addressing_style}}
        client_arguments = {
            "endpoint_url": endpoint_url,
            "region_name": os.environ.get("AWS_REGION") or None,
        }
        self.client = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4", **base_config),
            **client_arguments,
        )
        self.anonymous_client = boto3.client(
            "s3",
            config=Config(signature_version=UNSIGNED, **base_config),
            **client_arguments,
        )

    def _anonymous_read_is_denied(self, object_name: str) -> bool:
        try:
            self.anonymous_client.head_object(Bucket=self.bucket_name, Key=object_name)
        except ClientError as exc:
            error = exc.response.get("Error", {})
            status_code = str(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", ""))
            return str(error.get("Code", "")) in _ANONYMOUS_DENIAL_CODES or status_code in {
                "401",
                "403",
                "404",
            }
        return False

    def upload(self, content: bytes, object_name: str) -> bool:
        try:
            self.client.upload_fileobj(
                BytesIO(content),
                self.bucket_name,
                object_name,
                ExtraArgs={
                    "CacheControl": "no-store",
                    "ContentType": "text/csv",
                },
            )
            # Confirm the object exists with credentials before interpreting an
            # anonymous 404 as a privacy-preserving response.
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            if not self._anonymous_read_is_denied(object_name):
                self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
                logger.error("Import source upload rejected because anonymous access was allowed")
                return False
            return True
        except (BotoCoreError, ClientError, ImportStorageConfigurationError) as exc:
            logger.error("Import source upload failed with %s", type(exc).__name__)
            return False

    def read(self, object_name: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket_name, Key=object_name)
        return response["Body"].read()

    def delete(self, object_name: str) -> bool:
        if not object_name:
            return True
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except (BotoCoreError, ClientError) as exc:
            logger.error("Import source cleanup failed with %s", type(exc).__name__)
            return False


def upload_import_source(content: bytes, object_name: str) -> bool:
    try:
        return ImportSourceStorage().upload(content, object_name)
    except ImportStorageConfigurationError as exc:
        logger.error("Import source upload failed with %s", type(exc).__name__)
        return False


def read_import_source(object_name: str) -> bytes:
    return ImportSourceStorage().read(object_name)


def delete_import_source(object_name: str) -> bool:
    if not object_name:
        return True
    try:
        return ImportSourceStorage().delete(object_name)
    except ImportStorageConfigurationError as exc:
        logger.error("Import source cleanup failed with %s", type(exc).__name__)
        return False
