# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Outbound mail transport implementations."""

from .base import TransportReceipt
from .ses import SESAPITransport
from .smtp import SMTPTransport


def get_transport(provider: str):
    if provider == "ses_api":
        return SESAPITransport()
    return SMTPTransport()


__all__ = ["SESAPITransport", "SMTPTransport", "TransportReceipt", "get_transport"]
