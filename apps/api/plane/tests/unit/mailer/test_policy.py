# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.mailer.enums import MailDecision, MailPolicyClass
from plane.mailer.policy import resolve_mail_policy


@pytest.mark.unit
@pytest.mark.parametrize(
    "mail_class",
    [
        MailPolicyClass.ACCOUNT_ACCESS,
        MailPolicyClass.ACCOUNT_SECURITY,
        MailPolicyClass.EXTERNAL_INVITATION,
    ],
)
def test_essential_account_mail_is_always_clear(mail_class):
    result = resolve_mail_policy(
        mail_class,
        has_active_key=True,
        openpgp_enabled=True,
    )

    assert result.decision == MailDecision.CLEAR


@pytest.mark.unit
@pytest.mark.parametrize(
    "mail_class",
    [
        MailPolicyClass.PROJECT_NOTIFICATION,
        MailPolicyClass.EXPORT,
        MailPolicyClass.OPERATIONAL,
    ],
)
def test_confidential_mail_without_a_key_is_suppressed(mail_class):
    result = resolve_mail_policy(
        mail_class,
        has_active_key=False,
        openpgp_enabled=True,
    )

    assert result.decision == MailDecision.SUPPRESS


@pytest.mark.unit
def test_known_user_invitation_is_encrypted_when_a_key_exists():
    result = resolve_mail_policy(
        MailPolicyClass.KNOWN_USER_INVITATION,
        has_active_key=True,
        openpgp_enabled=True,
    )

    assert result.decision == MailDecision.ENCRYPT


@pytest.mark.unit
def test_openpgp_feature_flag_preserves_legacy_delivery_during_rollout():
    result = resolve_mail_policy(
        MailPolicyClass.PROJECT_NOTIFICATION,
        has_active_key=False,
        openpgp_enabled=False,
    )

    assert result.decision == MailDecision.CLEAR
