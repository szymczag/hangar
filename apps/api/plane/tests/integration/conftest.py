# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Fixtures for tests that use real external services rather than mocks.

Everything under ``plane/tests/unit`` means "no external services" -- every
storage test there patches ``S3Storage`` or ``boto3``. That meaning is worth
keeping, so tests that genuinely need an object store live here instead.
"""

import os
import uuid

import boto3
import pytest
from botocore.client import Config
from django.conf import settings


@pytest.fixture
def object_store():
    """A boto3 client built independently of the code under test.

    Deliberately not ``S3Storage``: a storage test that silently falls back to
    the same abstraction it is testing proves nothing. This one talks to the
    endpoint directly, so an assertion about a stored object is an assertion
    about the object store.

    Skips when no endpoint is configured, and **fails** when one is configured
    but unreachable. A silent skip is how a suite like this rots: it would go
    green forever the day the service stopped being started.
    """
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
    if not endpoint:
        pytest.skip("AWS_S3_ENDPOINT_URL is not set; no object store to talk to")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name=settings.AWS_REGION or "us-east-1",
    )
    bucket = settings.AWS_STORAGE_BUCKET_NAME

    # Loud rather than skipped: the endpoint was configured, so somebody meant
    # for this to run.
    client.head_bucket(Bucket=bucket)

    prefix = f"integration/{uuid.uuid4().hex}/"
    yield client, bucket, prefix

    listed = client.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
    for entry in listed:
        client.delete_object(Bucket=bucket, Key=entry["Key"])
