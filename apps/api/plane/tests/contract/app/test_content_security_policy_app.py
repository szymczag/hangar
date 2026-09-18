# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The API's own Content-Security-Policy and the endpoint that collects the
frontends' violation reports."""

import json

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

REPORT_URL = "/api/csp-report/"


def report(**fields):
    return json.dumps({"csp-report": {"document-uri": "https://hangar.example/", **fields}})


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.contract
@pytest.mark.django_db
class TestApiContentSecurityPolicy:
    def test_api_responses_allow_nothing(self):
        response = APIClient().get("/api/instances/")
        assert response["Content-Security-Policy"].startswith("default-src 'none'")
        assert "frame-ancestors 'none'" in response["Content-Security-Policy"]


@pytest.mark.contract
@pytest.mark.django_db
class TestCspReportEndpoint:
    def test_accepts_a_report_without_authentication_or_csrf(self, caplog):
        client = APIClient(enforce_csrf_checks=True)
        with caplog.at_level("WARNING", logger="plane.security.csp"):
            response = client.post(
                REPORT_URL,
                report(**{"effective-directive": "style-src-attr", "blocked-uri": "inline"}),
                content_type="application/csp-report",
            )

        assert response.status_code == 204
        record = next(r for r in caplog.records if r.name == "plane.security.csp")
        assert record.csp_report["effective-directive"] == "style-src-attr"

    def test_only_post(self):
        assert APIClient().get(REPORT_URL).status_code == 405

    def test_rejects_malformed_and_oversized_bodies(self):
        client = APIClient()
        assert client.post(REPORT_URL, "not json", content_type="application/csp-report").status_code == 400
        oversized = report(**{"blocked-uri": "x" * 20000})
        assert client.post(REPORT_URL, oversized, content_type="application/csp-report").status_code == 413

    def test_logging_is_rate_limited_per_client(self, caplog):
        client = APIClient()
        with caplog.at_level("WARNING", logger="plane.security.csp"):
            for _ in range(40):
                client.post(REPORT_URL, report(), content_type="application/csp-report")

        logged = [r for r in caplog.records if r.name == "plane.security.csp"]
        assert len(logged) == 30
