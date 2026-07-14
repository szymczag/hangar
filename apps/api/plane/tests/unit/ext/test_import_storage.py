# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.management import call_command
from django.core.management.base import CommandError

from plane.ext.utils.import_storage import ImportSourceStorage, upload_import_source


def _denied() -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "AccessDenied", "Message": "denied"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        },
        "HeadObject",
    )


class TestImportSourceStorage:
    @patch("plane.ext.utils.import_storage.boto3.client")
    def test_upload_uses_separate_internal_bucket_and_requires_anonymous_denial(
        self,
        client_factory,
        monkeypatch,
    ):
        signed_client = Mock()
        anonymous_client = Mock()
        anonymous_client.head_object.side_effect = _denied()
        client_factory.side_effect = [signed_client, anonymous_client]
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "public-uploads")
        monkeypatch.setenv("IMPORT_S3_BUCKET_NAME", "private-imports")
        monkeypatch.setenv("AWS_S3_ENDPOINT_URL", "http://object-storage:9000")
        monkeypatch.setenv("AWS_S3_PUBLIC_ENDPOINT_URL", "https://files.example.com")

        storage = ImportSourceStorage()

        assert storage.upload(b"csv", "imports/job/source.csv") is True
        signed_client.upload_fileobj.assert_called_once()
        assert signed_client.upload_fileobj.call_args.args[1:3] == (
            "private-imports",
            "imports/job/source.csv",
        )
        assert all(
            call.kwargs["endpoint_url"] == "http://object-storage:9000" for call in client_factory.call_args_list
        )
        signed_client.delete_object.assert_not_called()

    @patch("plane.ext.utils.import_storage.boto3.client")
    def test_upload_deletes_object_when_anonymous_lookup_succeeds(self, client_factory, monkeypatch):
        signed_client = Mock()
        anonymous_client = Mock()
        client_factory.side_effect = [signed_client, anonymous_client]
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "public-uploads")
        monkeypatch.setenv("IMPORT_S3_BUCKET_NAME", "private-imports")

        storage = ImportSourceStorage()

        assert storage.upload(b"csv", "imports/job/source.csv") is False
        signed_client.delete_object.assert_called_once_with(
            Bucket="private-imports",
            Key="imports/job/source.csv",
        )

    @patch("plane.ext.utils.import_storage.boto3.client")
    def test_public_upload_bucket_cannot_be_reused(self, client_factory, monkeypatch):
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "uploads")
        monkeypatch.setenv("IMPORT_S3_BUCKET_NAME", "uploads")

        assert upload_import_source(b"csv", "imports/job/source.csv") is False
        client_factory.assert_not_called()


class TestCreateImportBucketCommand:
    @patch("plane.ext.management.commands.create_import_bucket.boto3.client")
    def test_existing_dedicated_bucket_is_accepted(self, client_factory, monkeypatch):
        client = Mock()
        client_factory.return_value = client
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "public-uploads")
        monkeypatch.setenv("IMPORT_S3_BUCKET_NAME", "private-imports")

        call_command("create_import_bucket")

        client.head_bucket.assert_called_once_with(Bucket="private-imports")
        client.create_bucket.assert_not_called()

    @patch("plane.ext.management.commands.create_import_bucket.boto3.client")
    def test_public_bucket_cannot_be_reused(self, client_factory, monkeypatch):
        monkeypatch.setenv("AWS_S3_BUCKET_NAME", "uploads")
        monkeypatch.setenv("IMPORT_S3_BUCKET_NAME", "uploads")

        with pytest.raises(CommandError, match="separate bucket"):
            call_command("create_import_bucket")

        client_factory.assert_not_called()
