# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.test import override_settings

from plane.bgtasks.export_task import _public_s3_endpoint


@pytest.mark.unit
class TestPublicS3Endpoint:
    @override_settings(
        AWS_S3_PUBLIC_ENDPOINT_URL="https://objects.example.com",
        AWS_S3_URL_PROTOCOL="https:",
        AWS_S3_CUSTOM_DOMAIN="hangar.example.com/hangar",
    )
    def test_explicit_public_endpoint_takes_precedence(self):
        assert _public_s3_endpoint() == "https://objects.example.com"

    @override_settings(
        AWS_S3_PUBLIC_ENDPOINT_URL=None,
        AWS_S3_URL_PROTOCOL="https:",
        AWS_S3_CUSTOM_DOMAIN="hangar.example.com/uploads",
    )
    def test_legacy_application_origin_fallback_is_preserved(self):
        assert _public_s3_endpoint() == "https://hangar.example.com/"
