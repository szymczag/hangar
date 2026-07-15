# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import logging
from uuid import UUID

from plane.ext.models import ImportDispatch

from .services import (
    ImportDispatchUnavailable,
    mark_dispatch_failed,
    mark_dispatch_published,
    prepare_dispatch_attempt,
)


logger = logging.getLogger(__name__)


def publish_import_dispatch(dispatch_id: UUID, *, allow_stale_published: bool = False) -> bool:
    """Publish a durable dispatch without treating broker ambiguity as job failure."""

    try:
        attempt = prepare_dispatch_attempt(
            dispatch_id=dispatch_id,
            allow_stale_published=allow_stale_published,
        )
    except ImportDispatchUnavailable:
        return False

    try:
        from plane.ext.tasks import run_todoist_import

        run_todoist_import.apply_async(
            args=[str(attempt.job_id), attempt.generation],
            task_id=str(attempt.task_id),
        )
    except Exception:  # noqa: BLE001 - broker errors are reduced to a safe code
        mark_dispatch_failed(
            dispatch_id=attempt.dispatch_id,
            error_code=ImportDispatch.ErrorCode.PUBLISH_CONFIRMATION_UNKNOWN,
        )
        logger.warning("Todoist import dispatch publication was not confirmed")
        return False

    mark_dispatch_published(dispatch_id=attempt.dispatch_id)
    return True
