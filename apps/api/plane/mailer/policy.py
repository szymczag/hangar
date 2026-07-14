"""Central cleartext, encryption, and suppression policy."""

from dataclasses import dataclass

from .enums import MailDecision, MailPolicyClass


@dataclass(frozen=True)
class PolicyResult:
    decision: MailDecision
    reason: str


_ALWAYS_CLEAR = {
    MailPolicyClass.ACCOUNT_ACCESS,
    MailPolicyClass.ACCOUNT_SECURITY,
    MailPolicyClass.EXTERNAL_INVITATION,
}

_REQUIRE_ENCRYPTION = {
    MailPolicyClass.PROJECT_NOTIFICATION,
    MailPolicyClass.EXPORT,
    MailPolicyClass.OPERATIONAL,
    MailPolicyClass.KNOWN_USER_INVITATION,
}


def resolve_mail_policy(
    policy_class: MailPolicyClass,
    *,
    has_active_key: bool,
    openpgp_enabled: bool,
) -> PolicyResult:
    """Return the only permitted delivery behavior for a mail class."""

    if policy_class in _ALWAYS_CLEAR:
        return PolicyResult(MailDecision.CLEAR, "account_or_external_delivery")

    if not openpgp_enabled:
        return PolicyResult(MailDecision.CLEAR, "openpgp_not_enabled")

    if has_active_key:
        return PolicyResult(MailDecision.ENCRYPT, "active_verified_key")

    if policy_class in _REQUIRE_ENCRYPTION:
        return PolicyResult(MailDecision.SUPPRESS, "no_active_verified_key")

    return PolicyResult(MailDecision.CLEAR, "minimal_cleartext_allowed")
