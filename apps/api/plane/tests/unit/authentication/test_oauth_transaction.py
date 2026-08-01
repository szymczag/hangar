# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import MagicMock

from plane.authentication.utils.oauth_transaction import (
    consume_oauth_transaction,
    start_oauth_transaction,
)


def test_oauth_transaction_requires_non_empty_matching_state_and_is_single_use():
    request = MagicMock()
    request.session = {}
    state = start_oauth_transaction(
        request,
        "provider_app",
        host="https://hangar.example.com",
        next_path="/workspace/",
    )

    transaction, valid = consume_oauth_transaction(request, "provider_app", state)
    assert valid is True
    assert transaction["host"] == "https://hangar.example.com"
    assert transaction["next_path"] == "/workspace/"

    _transaction, replay_valid = consume_oauth_transaction(request, "provider_app", state)
    assert replay_valid is False


def test_oauth_transaction_rejects_blank_state_without_pending_session():
    request = MagicMock()
    request.session = {}

    _transaction, valid = consume_oauth_transaction(request, "provider_app", "")

    assert valid is False
