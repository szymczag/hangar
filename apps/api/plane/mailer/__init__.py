"""Policy-aware outbound email delivery for Hangar."""

from .enums import MailDecision, MailPolicyClass, OutboxStatus, SuppressionReason

__all__ = [
    "MailDecision",
    "MailPolicyClass",
    "OutboxStatus",
    "SuppressionReason",
]
