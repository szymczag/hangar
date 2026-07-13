# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
import re


HANGAR_REPOSITORY_URL = "https://github.com/szymczag/hangar"
_FULL_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")


def get_product_metadata() -> dict[str, str | None]:
    """Return public Hangar identity and operator-owned external links."""

    version = os.environ.get("APP_VERSION", "development").strip() or "development"
    revision = os.environ.get("HANGAR_SOURCE_REVISION", "").strip().lower()
    repository_url = os.environ.get("HANGAR_REPOSITORY_URL", HANGAR_REPOSITORY_URL).strip()

    configured_source_url = os.environ.get("HANGAR_SOURCE_URL", "").strip()
    if configured_source_url:
        source_url = configured_source_url
    elif _FULL_GIT_REVISION.fullmatch(revision):
        source_url = f"{repository_url}/tree/{revision}"
    else:
        source_url = repository_url

    return {
        "name": "Hangar",
        "version": version,
        "repository_url": repository_url,
        "source_url": source_url,
        "documentation_url": os.environ.get(
            "HANGAR_DOCUMENTATION_URL", f"{repository_url}#readme"
        ).strip(),
        "issues_url": os.environ.get(
            "HANGAR_ISSUES_URL", f"{repository_url}/issues"
        ).strip(),
        "security_url": os.environ.get(
            "HANGAR_SECURITY_URL", f"{repository_url}/security/advisories/new"
        ).strip(),
        "terms_url": os.environ.get("HANGAR_TERMS_URL", "").strip() or None,
        "privacy_url": os.environ.get("HANGAR_PRIVACY_URL", "").strip() or None,
    }
