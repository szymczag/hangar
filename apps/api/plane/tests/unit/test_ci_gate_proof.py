# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Temporary. Proves the API gate goes red when a test fails. Not for merge."""


def test_this_is_meant_to_fail():
    assert 1 == 2, "deliberate failure proving the gate reports it"
