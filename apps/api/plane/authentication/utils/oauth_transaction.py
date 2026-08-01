# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hmac
import secrets
import time

OAUTH_TRANSACTION_TTL = 60 * 10


def start_oauth_transaction(request, key, *, host, next_path):
    state = secrets.token_urlsafe(32)
    request.session[key] = {
        "state": state,
        "host": host,
        "next_path": next_path,
        "created_at": time.time(),
    }
    return state


def consume_oauth_transaction(request, key, state):
    transaction = request.session.pop(key, None) or {}
    expected_state = transaction.get("state")
    created_at = transaction.get("created_at")
    age = time.time() - created_at if isinstance(created_at, (int, float)) else None
    valid = bool(
        state
        and expected_state
        and hmac.compare_digest(state, expected_state)
        and age is not None
        and 0 <= age <= OAUTH_TRANSACTION_TTL
    )
    return transaction, valid
