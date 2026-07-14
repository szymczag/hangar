"""Allowlisted mail templates and immutable policy metadata."""

from dataclasses import dataclass

from .enums import MailPolicyClass
from .exceptions import MailPolicyError


@dataclass(frozen=True)
class MailTemplateDefinition:
    policy_class: MailPolicyClass
    configuration_set_kind: str
    audit_label: str
    include_security_notice: bool = False


MAIL_TEMPLATES: dict[str, MailTemplateDefinition] = {
    "auth.magic_signin": MailTemplateDefinition(MailPolicyClass.ACCOUNT_ACCESS, "auth", "Login code", True),
    "auth.forgot_password": MailTemplateDefinition(MailPolicyClass.ACCOUNT_ACCESS, "auth", "Password reset", True),
    "account.activation": MailTemplateDefinition(MailPolicyClass.ACCOUNT_SECURITY, "auth", "Account activation", True),
    "account.deactivation": MailTemplateDefinition(
        MailPolicyClass.ACCOUNT_SECURITY, "auth", "Account deactivation", True
    ),
    "account.email_update_code": MailTemplateDefinition(
        MailPolicyClass.ACCOUNT_ACCESS, "auth", "Email change code", True
    ),
    "account.email_updated": MailTemplateDefinition(MailPolicyClass.ACCOUNT_SECURITY, "auth", "Email changed", True),
    "invitation.workspace": MailTemplateDefinition(
        MailPolicyClass.EXTERNAL_INVITATION, "auth", "Workspace invitation", True
    ),
    "invitation.workspace_known": MailTemplateDefinition(
        MailPolicyClass.KNOWN_USER_INVITATION, "auth", "Workspace invitation"
    ),
    "invitation.project": MailTemplateDefinition(
        MailPolicyClass.EXTERNAL_INVITATION, "auth", "Project invitation", True
    ),
    "invitation.project_known": MailTemplateDefinition(
        MailPolicyClass.KNOWN_USER_INVITATION, "auth", "Project invitation"
    ),
    "project.member_added": MailTemplateDefinition(
        MailPolicyClass.KNOWN_USER_INVITATION, "notifications", "Project membership"
    ),
    "notification.issue_updates": MailTemplateDefinition(
        MailPolicyClass.PROJECT_NOTIFICATION, "notifications", "Work item updates"
    ),
    "export.analytics": MailTemplateDefinition(MailPolicyClass.EXPORT, "notifications", "Analytics export"),
    "operational.webhook_deactivated": MailTemplateDefinition(
        MailPolicyClass.OPERATIONAL, "notifications", "Webhook disabled"
    ),
    "security.openpgp_challenge": MailTemplateDefinition(
        MailPolicyClass.PROJECT_NOTIFICATION, "auth", "OpenPGP verification"
    ),
    "security.openpgp_test": MailTemplateDefinition(
        MailPolicyClass.PROJECT_NOTIFICATION, "auth", "Encrypted email test"
    ),
    "security.openpgp_changed": MailTemplateDefinition(
        MailPolicyClass.ACCOUNT_SECURITY, "auth", "Email security changed", True
    ),
    "diagnostic.test": MailTemplateDefinition(MailPolicyClass.ACCOUNT_SECURITY, "auth", "Administrator email test"),
}


def get_template_definition(template_key: str) -> MailTemplateDefinition:
    try:
        return MAIL_TEMPLATES[template_key]
    except KeyError as exc:
        raise MailPolicyError("The requested email template is not registered") from exc
