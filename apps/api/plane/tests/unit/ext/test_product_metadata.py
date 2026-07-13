# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.ext.product_metadata import HANGAR_REPOSITORY_URL
from plane.ext.product_metadata import get_product_metadata


def test_product_metadata_uses_hangar_defaults(monkeypatch):
    for key in (
        "APP_VERSION",
        "HANGAR_REPOSITORY_URL",
        "HANGAR_SOURCE_REVISION",
        "HANGAR_SOURCE_URL",
        "HANGAR_DOCUMENTATION_URL",
        "HANGAR_ISSUES_URL",
        "HANGAR_SECURITY_URL",
        "HANGAR_TERMS_URL",
        "HANGAR_PRIVACY_URL",
    ):
        monkeypatch.delenv(key, raising=False)

    metadata = get_product_metadata()

    assert metadata == {
        "name": "Hangar",
        "version": "development",
        "repository_url": HANGAR_REPOSITORY_URL,
        "source_url": HANGAR_REPOSITORY_URL,
        "documentation_url": f"{HANGAR_REPOSITORY_URL}#readme",
        "issues_url": f"{HANGAR_REPOSITORY_URL}/issues",
        "security_url": f"{HANGAR_REPOSITORY_URL}/security/advisories/new",
        "terms_url": None,
        "privacy_url": None,
    }


def test_product_metadata_exposes_exact_revision_and_operator_links(monkeypatch):
    revision = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("APP_VERSION", "v0.2.0-rc.1")
    monkeypatch.setenv("HANGAR_SOURCE_REVISION", revision.upper())
    monkeypatch.setenv("HANGAR_DOCUMENTATION_URL", "https://docs.example.com/hangar")
    monkeypatch.setenv("HANGAR_ISSUES_URL", "https://git.example.com/hangar/issues")
    monkeypatch.setenv("HANGAR_SECURITY_URL", "https://git.example.com/hangar/security")
    monkeypatch.setenv("HANGAR_TERMS_URL", "https://example.com/terms")
    monkeypatch.setenv("HANGAR_PRIVACY_URL", "https://example.com/privacy")

    metadata = get_product_metadata()

    assert metadata["source_url"] == f"{HANGAR_REPOSITORY_URL}/tree/{revision}"
    assert metadata["version"] == "v0.2.0-rc.1"
    assert metadata["documentation_url"] == "https://docs.example.com/hangar"
    assert metadata["issues_url"] == "https://git.example.com/hangar/issues"
    assert metadata["security_url"] == "https://git.example.com/hangar/security"
    assert metadata["terms_url"] == "https://example.com/terms"
    assert metadata["privacy_url"] == "https://example.com/privacy"


def test_explicit_source_url_wins_over_revision(monkeypatch):
    monkeypatch.setenv("HANGAR_SOURCE_REVISION", "a" * 40)
    monkeypatch.setenv("HANGAR_SOURCE_URL", "https://source.example.com/hangar/revision")

    assert get_product_metadata()["source_url"] == "https://source.example.com/hangar/revision"
