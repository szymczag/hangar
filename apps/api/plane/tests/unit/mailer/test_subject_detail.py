# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
The outer Subject of an encrypted notification.

Everything else in a PGP/MIME message is inside the encrypted entity. The outer
Subject is not: it reaches the mail provider, its logs and its backups in the
clear. An operator can trade that confidentiality for an inbox people can
triage, but only deliberately -- so the default has to stay generic, and what
the descriptive form reveals has to be exactly what was asked for and no more.
"""

from email import policy
from email.parser import BytesParser
from unittest.mock import patch

import pytest

from plane.bgtasks.email_notification_task import MAX_OUTER_SUBJECT_TITLE, describe_notification
from plane.mailer.mime import GENERIC_ENCRYPTED_SUBJECT, build_encrypted_message


@pytest.mark.unit
class TestDescribeNotification:
    def test_it_names_the_work_item_and_the_commenter(self):
        assert (
            describe_notification("INFRA-3", "Broken login flow", ["Ada L"])
            == "INFRA-3 updates: Broken login flow - new comment from Ada L"
        )

    def test_several_commenters_are_summarised_rather_than_listed(self):
        """A subject naming eight people is unreadable and leaks all eight."""
        described = describe_notification("INFRA-3", "Broken login flow", ["Ada L", "Bo K", "Cy N"])
        assert described == "INFRA-3 updates: Broken login flow - new comment from Ada L and 2 more"

    def test_without_comments_it_says_only_that_something_changed(self):
        assert describe_notification("INFRA-3", "Broken login flow", []) == "INFRA-3 updates: Broken login flow"

    def test_a_long_title_is_truncated(self):
        described = describe_notification("INFRA-3", "x" * 400, [])
        assert len(described) < 200
        assert described.endswith("…")

    def test_control_characters_cannot_reach_the_header(self):
        """A header injection here would be a header injection in the clear."""
        described = describe_notification("INFRA-3", "Broken\r\nBcc: attacker@example.com", ["Ada\r\nL"])
        assert "\r" not in described
        assert "\n" not in described

    def test_a_missing_title_still_produces_a_usable_subject(self):
        assert describe_notification("INFRA-3", "", []) == "INFRA-3 updates"


@pytest.mark.unit
class TestOuterSubjectOnTheMessage:
    def _build(self, **kwargs):
        with patch("plane.mailer.mime.encrypt_for_certificate", return_value=b"-----BEGIN PGP MESSAGE-----"):
            return build_encrypted_message(
                inner_subject="Confidential project title",
                text_body="Confidential body",
                html_body="<p>Confidential body</p>",
                sender="Hangar <hello@hangar.example.com>",
                recipient="person@example.com",
                message_id="<message@hangar.example.com>",
                certificate="public certificate",
                encryption_subkey_fingerprint="A" * 40,
                **kwargs,
            )

    def test_the_default_reveals_nothing(self):
        message = self._build()
        assert message["Subject"] == GENERIC_ENCRYPTED_SUBJECT

    def test_a_descriptive_subject_is_used_when_given(self):
        message = self._build(outer_subject="INFRA-3 updates: Broken login flow")
        assert message["Subject"] == "INFRA-3 updates: Broken login flow"

    def test_an_empty_subject_falls_back_rather_than_sending_a_blank_header(self):
        message = self._build(outer_subject="")
        assert message["Subject"] == GENERIC_ENCRYPTED_SUBJECT

    def test_the_body_stays_encrypted_either_way(self):
        """The trade is the Subject alone; nothing else may leak with it."""
        message = self._build(outer_subject="INFRA-3 updates: Broken login flow")
        rendered = message.as_string()
        assert "Confidential body" not in rendered
        assert "Confidential project title" not in rendered

    def test_the_inner_subject_is_unaffected_by_the_outer_one(self):
        with patch("plane.mailer.mime.encrypt_for_certificate", return_value=b"x") as encrypt:
            build_encrypted_message(
                inner_subject="Confidential project title",
                outer_subject="INFRA-3 updates",
                text_body="Confidential body",
                html_body="<p>Confidential body</p>",
                sender="Hangar <hello@hangar.example.com>",
                recipient="person@example.com",
                message_id="<message@hangar.example.com>",
                certificate="public certificate",
                encryption_subkey_fingerprint="A" * 40,
            )
        inner = BytesParser(policy=policy.default).parsebytes(encrypt.call_args.args[0])
        assert inner["Subject"] == "Confidential project title"


@pytest.mark.unit
def test_the_truncation_limit_is_shorter_than_the_header_limit():
    """998 is the RFC limit; the title alone must leave room for the rest."""
    assert MAX_OUTER_SUBJECT_TITLE < 998
