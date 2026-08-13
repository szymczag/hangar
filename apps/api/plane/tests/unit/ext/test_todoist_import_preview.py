# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from freezegun import freeze_time
import pytest

from plane.ext.imports.preview import ImportPreviewTokenError, issue_preview_token, validate_preview_token


@pytest.mark.unit
def test_preview_token_is_bound_and_expires(settings):
    settings.TODOIST_IMPORT_PREVIEW_TTL_SECONDS = 60
    actor_id = uuid4()
    workspace_id = uuid4()
    project_id = uuid4()
    digest = "a" * 64
    issued_at = datetime(2026, 8, 13, tzinfo=timezone.utc)

    with freeze_time(issued_at):
        token = issue_preview_token(
            actor_id=actor_id,
            workspace_id=workspace_id,
            project_id=project_id,
            source_digest=digest,
        )
        grant = validate_preview_token(
            token,
            actor_id=actor_id,
            workspace_id=workspace_id,
            project_id=project_id,
            source_digest=digest,
        )

    assert grant.nonce

    with freeze_time(issued_at), pytest.raises(ImportPreviewTokenError, match="does not match"):
        validate_preview_token(
            token,
            actor_id=actor_id,
            workspace_id=workspace_id,
            project_id=uuid4(),
            source_digest=digest,
        )

    with freeze_time(issued_at + timedelta(seconds=61)), pytest.raises(ImportPreviewTokenError, match="expired"):
        validate_preview_token(
            token,
            actor_id=actor_id,
            workspace_id=workspace_id,
            project_id=project_id,
            source_digest=digest,
        )
