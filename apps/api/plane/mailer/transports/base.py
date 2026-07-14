# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Transport contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransportReceipt:
    provider_message_id: str = ""
