# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from plane.license.bgtasks.telemetry_metrics import _collect_and_push_metrics
from plane.license.management.commands.register_instance import (
    MAX_RELEASE_RESPONSE_BYTES,
    Command,
    normalize_hangar_release_tag,
    normalize_product_version,
)
from plane.license.models import Instance


class _Response:
    def __init__(self, payload=None, *, status_code=200, chunks=None):
        self.status_code = status_code
        self._chunks = chunks if chunks is not None else [json.dumps(payload).encode("utf-8")]
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


@pytest.mark.unit
class TestReleaseCheckPrivacy:
    def test_release_check_is_offline_by_default(self, monkeypatch):
        monkeypatch.delenv("HANGAR_RELEASE_CHECK_URL", raising=False)

        with patch("plane.license.management.commands.register_instance.pinned_fetch") as fetch:
            assert Command().check_for_latest_version("v1.2.3") == "v1.2.3"

        fetch.assert_not_called()

    @pytest.mark.parametrize(
        "url",
        [
            "http://releases.example.com/latest",
            "https://user:password@releases.example.com/latest",
            "https://releases.example.com/latest#fragment",
        ],
    )
    def test_release_check_rejects_unsafe_url_shapes(self, monkeypatch, url):
        monkeypatch.setenv("HANGAR_RELEASE_CHECK_URL", url)

        with patch("plane.license.management.commands.register_instance.pinned_fetch") as fetch:
            assert Command().check_for_latest_version("v1.2.3") == "v1.2.3"

        fetch.assert_not_called()

    def test_release_check_uses_ssrf_safe_pinned_client(self, monkeypatch):
        url = "https://api.github.com/repos/szymczag/hangar/releases/latest"
        monkeypatch.setenv("HANGAR_RELEASE_CHECK_URL", url)
        response = _Response({"tag_name": "hangar-v1.3.0"})

        with patch(
            "plane.license.management.commands.register_instance.pinned_fetch",
            return_value=response,
        ) as fetch:
            assert Command().check_for_latest_version("v1.2.3") == "v1.3.0"

        fetch.assert_called_once_with(
            "GET",
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "hangar-release-check",
            },
            timeout=10,
            stream=True,
        )
        assert response.closed is True

    @pytest.mark.parametrize(
        ("tag_name", "expected"),
        [
            ("hangar-v1.3.0", "v1.3.0"),
            ("hangar-v0.1.0-alpha.1", "v0.1.0-alpha.1"),
            ("hangar-v0.1.0-beta.2", "v0.1.0-beta.2"),
            ("hangar-v0.1.0-rc.3", "v0.1.0-rc.3"),
            ("v1.3.0", None),
            ("hangar-v01.3.0", None),
            ("hangar-v1.3.0-dev.1", None),
            (" hangar-v1.3.0", None),
            ("hangar-v1.3.0\n", None),
            (None, None),
        ],
    )
    def test_release_tag_normalization_is_namespaced_and_strict(self, tag_name, expected):
        assert normalize_hangar_release_tag(tag_name) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("v1.2.3", "v1.2.3"),
            ("1.2.3", "v1.2.3"),
            ("v0.1.0-rc.1", "v0.1.0-rc.1"),
            ("hangar-v1.2.3", None),
            ("1.2", None),
            (None, None),
        ],
    )
    def test_product_version_normalization(self, value, expected):
        assert normalize_product_version(value) == expected

    @pytest.mark.parametrize("tag_name", ["v1.3.0", "hangar-v1.3.0-dev.1", "hangar-v01.3.0"])
    def test_release_check_rejects_untrusted_tag_names(self, monkeypatch, tag_name):
        monkeypatch.setenv(
            "HANGAR_RELEASE_CHECK_URL",
            "https://api.github.com/repos/szymczag/hangar/releases/latest",
        )
        response = _Response({"tag_name": tag_name})

        with patch(
            "plane.license.management.commands.register_instance.pinned_fetch",
            return_value=response,
        ):
            assert Command().check_for_latest_version("v1.2.3") == "v1.2.3"

        assert response.closed is True

    def test_current_version_prefers_packaged_hangar_version(self, monkeypatch):
        monkeypatch.setenv("APP_VERSION", "v0.2.0-rc.1")

        assert Command().check_for_current_version() == "v0.2.0-rc.1"

    def test_current_version_rejects_invalid_environment_value(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APP_VERSION", "hangar-v9.9.9")
        monkeypatch.chdir(tmp_path)

        assert Command().check_for_current_version() == "v0.1.0"

    def test_release_check_fails_closed_when_ssrf_validation_rejects_target(self, monkeypatch):
        monkeypatch.setenv("HANGAR_RELEASE_CHECK_URL", "https://metadata.example/latest")

        with patch(
            "plane.license.management.commands.register_instance.pinned_fetch",
            side_effect=ValueError("Access to private/internal networks is not allowed"),
        ):
            assert Command().check_for_latest_version("v1.2.3") == "v1.2.3"

    def test_release_check_rejects_redirects(self, monkeypatch):
        monkeypatch.setenv("HANGAR_RELEASE_CHECK_URL", "https://releases.example.com/latest")
        response = _Response(status_code=302)

        with patch(
            "plane.license.management.commands.register_instance.pinned_fetch",
            return_value=response,
        ):
            assert Command().check_for_latest_version("v1.2.3") == "v1.2.3"

        assert response.closed is True

    def test_release_check_caps_response_size(self, monkeypatch):
        monkeypatch.setenv("HANGAR_RELEASE_CHECK_URL", "https://releases.example.com/latest")
        response = _Response(chunks=[b"x" * (MAX_RELEASE_RESPONSE_BYTES + 1)])

        with patch(
            "plane.license.management.commands.register_instance.pinned_fetch",
            return_value=response,
        ):
            assert Command().check_for_latest_version("v1.2.3") == "v1.2.3"

        assert response.closed is True


@pytest.mark.unit
class TestTelemetryPrivacy:
    def test_model_default_is_disabled(self):
        assert Instance._meta.get_field("is_telemetry_enabled").default is False

    def test_enabled_toggle_without_endpoint_does_not_create_exporter(self, monkeypatch):
        monkeypatch.delenv("OTLP_ENDPOINT", raising=False)
        instance = MagicMock(is_telemetry_enabled=True)

        with (
            patch("plane.license.bgtasks.telemetry_metrics.Instance.objects.first", return_value=instance),
            patch("plane.license.bgtasks.telemetry_metrics._create_otlp_metric_exporter") as exporter,
        ):
            _collect_and_push_metrics()

        exporter.assert_not_called()

    def test_disabled_toggle_does_not_resolve_configured_endpoint(self, monkeypatch):
        monkeypatch.setenv("OTLP_ENDPOINT", "https://otel.example.com")
        instance = MagicMock(is_telemetry_enabled=False)

        with (
            patch("plane.license.bgtasks.telemetry_metrics.Instance.objects.first", return_value=instance),
            patch("plane.license.bgtasks.telemetry_metrics.get_otlp_metric_export_configuration") as configuration,
        ):
            _collect_and_push_metrics()

        configuration.assert_not_called()

    def test_registration_creates_offline_hangar_instance(self, monkeypatch):
        monkeypatch.delenv("HANGAR_RELEASE_CHECK_URL", raising=False)
        command = Command()

        with (
            patch.object(command, "check_for_current_version", return_value="v1.2.3"),
            patch("plane.license.management.commands.register_instance.Instance.objects.first", return_value=None),
            patch("plane.license.management.commands.register_instance.Instance.objects.create") as create,
        ):
            command.handle(machine_signature="machine-signature")

        created = create.call_args.kwargs
        assert created["instance_name"] == "Hangar"
        assert created["current_version"] == "v1.2.3"
        assert created["latest_version"] == "v1.2.3"
        assert created["is_telemetry_enabled"] is False
