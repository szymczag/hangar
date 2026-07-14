# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.core.management import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the dedicated private bucket for short-lived import sources"

    def handle(self, *args, **options):
        main_bucket = os.environ.get("AWS_S3_BUCKET_NAME", "uploads").strip()
        bucket_name = os.environ.get("IMPORT_S3_BUCKET_NAME", f"{main_bucket}-imports").strip()
        if not bucket_name or bucket_name == main_bucket:
            raise CommandError("IMPORT_S3_BUCKET_NAME must name a separate bucket.")

        endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL") or os.environ.get("MINIO_ENDPOINT_URL")
        addressing_style = "path" if os.environ.get("USE_MINIO") == "1" else "auto"
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION") or None,
            config=Config(signature_version="s3v4", s3={"addressing_style": addressing_style}),
        )

        try:
            client.head_bucket(Bucket=bucket_name)
        except ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code not in {"404", "NoSuchBucket", "NotFound"} and status_code != 404:
                raise CommandError("The import bucket cannot be accessed.") from exc

            create_arguments = {"Bucket": bucket_name}
            region = os.environ.get("AWS_REGION", "")
            if not endpoint_url and region and region != "us-east-1":
                create_arguments["CreateBucketConfiguration"] = {"LocationConstraint": region}
            try:
                client.create_bucket(**create_arguments)
            except ClientError as create_error:
                raise CommandError("The import bucket could not be created.") from create_error

        self.stdout.write(self.style.SUCCESS(f"Private import bucket '{bucket_name}' is available."))
