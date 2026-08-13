# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured


PREVIEW_TOKEN_SALT = "plane.ext.todoist-import-preview.v1"


class ImportPreviewTokenError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ImportPreviewGrant:
    nonce: UUID


def _preview_ttl_seconds() -> int:
    try:
        value = int(getattr(settings, "TODOIST_IMPORT_PREVIEW_TTL_SECONDS"))
    except (AttributeError, TypeError, ValueError) as error:
        raise ImproperlyConfigured("TODOIST_IMPORT_PREVIEW_TTL_SECONDS must be an integer") from error
    if value < 60 or value > 3600:
        raise ImproperlyConfigured("TODOIST_IMPORT_PREVIEW_TTL_SECONDS must be between 60 and 3600")
    return value


def issue_preview_token(*, actor_id: UUID, workspace_id: UUID, project_id: UUID, source_digest: str) -> str:
    return signing.dumps(
        {
            "v": 1,
            "nonce": str(uuid4()),
            "actor_id": str(actor_id),
            "workspace_id": str(workspace_id),
            "project_id": str(project_id),
            "source_digest": source_digest,
        },
        salt=PREVIEW_TOKEN_SALT,
        compress=True,
    )


def validate_preview_token(
    token: object,
    *,
    actor_id: UUID,
    workspace_id: UUID,
    project_id: UUID,
    source_digest: str,
) -> ImportPreviewGrant:
    if not isinstance(token, str) or not token:
        raise ImportPreviewTokenError("A server-issued import preview is required.")
    try:
        payload = signing.loads(token, salt=PREVIEW_TOKEN_SALT, max_age=_preview_ttl_seconds())
    except signing.SignatureExpired as error:
        raise ImportPreviewTokenError("The import preview expired.") from error
    except signing.BadSignature as error:
        raise ImportPreviewTokenError("The import preview is invalid.") from error
    if not isinstance(payload, dict) or set(payload) != {
        "v",
        "nonce",
        "actor_id",
        "workspace_id",
        "project_id",
        "source_digest",
    }:
        raise ImportPreviewTokenError("The import preview is invalid.")
    expected = {
        "v": 1,
        "actor_id": str(actor_id),
        "workspace_id": str(workspace_id),
        "project_id": str(project_id),
        "source_digest": source_digest,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ImportPreviewTokenError("The import preview does not match this import.")
    try:
        nonce = UUID(str(payload["nonce"]))
    except (TypeError, ValueError) as error:
        raise ImportPreviewTokenError("The import preview is invalid.") from error
    return ImportPreviewGrant(nonce=nonce)
