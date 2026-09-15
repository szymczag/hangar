# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Two things a recipient sees before they read anything.

The receipt line is the last thing in the message and used to be set in the
document's default type with a rule above it, so it read as a separate block
bolted onto the end rather than as the footer's last line. The templates do not
agree on a footer size, so it takes the quietest of them.

The From line is what an inbox shows before the subject. A display name has
always been passed through to the header unchanged; nothing in the console said
so, and the field suggested a bare address, so instances sent as a bare mailbox.
These tests pin the behaviour so the console's new wording stays true.
"""

from email import policy
from email.parser import BytesParser
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from plane.mailer.mime import build_clear_message, sanitize_email_html

RECEIPT = "AAAA-BBBB-CCCC-DDDD-EEEE"


def _message(sender="Hangar <hello@hangar.example.com>", html_body="<body><p>Body</p></body>"):
    return build_clear_message(
        subject="Subject",
        text_body="Body",
        html_body=html_body,
        sender=sender,
        recipient="person@example.com",
        message_id="<message@hangar.example.com>",
        receipt_code=RECEIPT,
    )


def _html_of(message):
    return message.get_body(preferencelist=("html",)).get_content()


@pytest.mark.unit
class TestReceiptPresentation:
    def test_the_receipt_is_the_last_thing_in_the_message(self):
        soup = BeautifulSoup(_html_of(_message()), "html.parser")
        last = [element for element in (soup.body or soup).find_all(recursive=False)][-1]
        assert RECEIPT in last.get_text()

    def test_it_is_set_quietly_rather_than_in_body_type(self):
        """It is a reference number, not a sentence anyone reads first."""
        soup = BeautifulSoup(_html_of(_message()), "html.parser")
        receipt = soup.find(string=lambda text: RECEIPT in str(text)).parent
        style = receipt.get("style", "")
        assert "font-size:12px" in style
        assert "color:#5f5e5e" in style

    def test_it_clears_the_floated_footer_icons(self):
        """The notification footer floats its icons right; without this the
        receipt sits beside them instead of underneath."""
        soup = BeautifulSoup(_html_of(_message()), "html.parser")
        receipt = soup.find(string=lambda text: RECEIPT in str(text)).parent
        assert "clear:both" in receipt.get("style", "")

    def test_it_no_longer_draws_a_rule_above_itself(self):
        """The rule is what made it read as a separate block."""
        soup = BeautifulSoup(_html_of(_message()), "html.parser")
        receipt = soup.find(string=lambda text: RECEIPT in str(text)).parent
        assert "border-top" not in receipt.get("style", "")

    def test_it_survives_the_sanitizer(self):
        """Inline styles are kept unless they fetch something; this fetches nothing."""
        cleaned = sanitize_email_html(_html_of(_message()))
        assert RECEIPT in cleaned
        assert "font-size:12px" in cleaned

    def test_the_plain_text_part_still_carries_it(self):
        text = _message().get_body(preferencelist=("plain",)).get_content()
        assert text.rstrip().endswith(f"Hangar email receipt: {RECEIPT}")

    def test_a_message_without_a_receipt_gains_nothing(self):
        message = build_clear_message(
            subject="Subject",
            text_body="Body",
            html_body="<body><p>Body</p></body>",
            sender="Hangar <hello@hangar.example.com>",
            recipient="person@example.com",
            message_id="<message@hangar.example.com>",
        )
        assert "email receipt" not in _html_of(message)


@pytest.mark.unit
class TestSenderDisplayName:
    @pytest.mark.parametrize(
        "sender",
        [
            "hello@hangar.example.com",
            "Hangar Notifications <hello@hangar.example.com>",
            "Hangar Powiadomienia <hello@hangar.example.com>",
            '"Hangar, Notifications" <hello@hangar.example.com>',
        ],
    )
    def test_the_configured_sender_reaches_the_header_unchanged(self, sender):
        rendered = _message(sender=sender).as_bytes(policy=policy.SMTP)
        parsed = BytesParser(policy=policy.SMTP).parsebytes(rendered)
        assert str(parsed["From"]) == sender

    def test_a_display_name_is_accepted_by_the_sender_check(self):
        from plane.mailer.service import _configured_sender

        configured = "Hangar Notifications <hello@hangar.example.com>"
        with patch(
            "plane.mailer.service.get_email_configuration",
            return_value=("host", "user", "password", "587", "1", "0", configured),
        ):
            assert _configured_sender() == configured

    def test_a_sender_with_no_usable_address_is_refused(self):
        from plane.mailer.exceptions import MailPolicyError
        from plane.mailer.service import _configured_sender

        with patch(
            "plane.mailer.service.get_email_configuration",
            return_value=("host", "user", "password", "587", "1", "0", "Hangar Notifications"),
        ):
            with pytest.raises(MailPolicyError):
                _configured_sender()

    def test_a_display_name_cannot_smuggle_a_header(self):
        """The name is attacker-adjacent input in a console field."""
        from plane.mailer.exceptions import MailPolicyError
        from plane.mailer.service import _configured_sender

        with patch(
            "plane.mailer.service.get_email_configuration",
            return_value=("host", "user", "password", "587", "1", "0", "Evil\r\nBcc: x@example.com <a@example.com>"),
        ):
            with pytest.raises(MailPolicyError):
                _configured_sender()
