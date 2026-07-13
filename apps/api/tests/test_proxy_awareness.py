# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.test import RequestFactory, override_settings


@override_settings(
    ALLOWED_HOSTS=["hangar.example.com"],
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    USE_X_FORWARDED_HOST=True,
    USE_X_FORWARDED_PORT=True,
)
def test_trusted_proxy_headers_produce_canonical_external_url():
    request = RequestFactory().get(
        "/api/instances/",
        HTTP_HOST="hangar-api:8000",
        HTTP_X_FORWARDED_PROTO="https",
        HTTP_X_FORWARDED_HOST="hangar.example.com",
        HTTP_X_FORWARDED_PORT="443",
    )

    assert request.is_secure()
    assert request.get_host() == "hangar.example.com"
    assert request.get_port() == "443"
    assert request.build_absolute_uri() == "https://hangar.example.com/api/instances/"
