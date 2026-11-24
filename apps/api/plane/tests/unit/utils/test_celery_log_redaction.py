# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The worker's JSON log must not carry task arguments.

Celery logs "Task <name>[<id>] received" with the task's argsrepr and
kwargsrepr in ``extra={"data": ...}``; the JSON formatter printed them, so a
password-reset token or a sign-in code was in the worker's INFO log.
"""

import io
import json
import logging

import pytest
from celery.app import trace as celery_trace

from plane import celery as plane_celery
from plane.utils.logging import RedactTaskArgumentsFilter

SECRET = "reset-token-6f1c2b"


def _emit_received_line(handler):
    """Log the received line exactly as celery.worker.strategy does."""
    logger = logging.getLogger("celery.worker.strategy.test")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    context = {
        "id": "8a1d",
        "name": "plane.bgtasks.forgot_password_task.forgot_password",
        "args": f"('Ada', 'ada@example.com', 'MQ', '{SECRET}', 'https://hangar.test')",
        "kwargs": f"{{'token': '{SECRET}'}}",
        "eta": None,
    }
    logger.info(celery_trace.LOG_RECEIVED, context, extra={"data": context})


@pytest.mark.unit
@pytest.mark.parametrize("signal_handler", [plane_celery.setup_loggers, plane_celery.setup_task_loggers])
def test_the_worker_json_handlers_drop_task_arguments(signal_handler):
    target = logging.getLogger(f"hangar.test.{signal_handler.__name__}")
    target.handlers = []
    signal_handler(target)
    (handler,) = target.handlers
    stream = io.StringIO()
    handler.setStream(stream)

    _emit_received_line(handler)

    line = stream.getvalue()
    assert SECRET not in line
    record = json.loads(line.split("\n")[0])
    assert record["data"]["args"] == RedactTaskArgumentsFilter.REDACTED
    assert record["data"]["kwargs"] == RedactTaskArgumentsFilter.REDACTED
    # The line stays traceable.
    assert record["data"]["name"].endswith("forgot_password")
    assert record["data"]["id"] == "8a1d"
    assert "received" in record["message"]


@pytest.mark.unit
def test_records_without_task_context_pass_unchanged():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "plain %s", ("message",), None)
    record.data = {"other": "value"}
    assert RedactTaskArgumentsFilter().filter(record) is True
    assert record.getMessage() == "plain message"
    assert record.data == {"other": "value"}
