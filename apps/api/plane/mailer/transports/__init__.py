"""Outbound mail transport implementations."""

from .base import TransportReceipt
from .ses import SESAPITransport
from .smtp import SMTPTransport


def get_transport(provider: str):
    if provider == "ses_api":
        return SESAPITransport()
    return SMTPTransport()


__all__ = ["SESAPITransport", "SMTPTransport", "TransportReceipt", "get_transport"]
