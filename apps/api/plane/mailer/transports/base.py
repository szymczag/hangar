"""Transport contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TransportReceipt:
    provider_message_id: str = ""
