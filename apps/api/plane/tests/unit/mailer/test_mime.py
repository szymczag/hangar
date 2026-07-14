# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from email import policy
from email.parser import BytesParser
from unittest.mock import patch

import pytest

from plane.mailer.mime import SECURITY_NOTICE_TEXT, build_clear_message, build_encrypted_message, sanitize_email_html


@pytest.mark.unit
def test_required_cleartext_mail_has_security_notice_and_no_header_injection():
    message = build_clear_message(
        subject="Reset your password",
        text_body="Use the link.",
        html_body="<p>Use the link.</p>",
        sender="Hangar <hello@hangar.example.com>",
        recipient="person@example.com",
        message_id="<message@hangar.example.com>",
        include_security_notice=True,
        receipt_code="AAAA-BBBB-CCCC-DDDD-EEEE",
    )

    parsed = BytesParser(policy=policy.default).parsebytes(message.as_bytes(policy=policy.SMTP))
    text = parsed.get_body(preferencelist=("plain",)).get_content()
    html = parsed.get_body(preferencelist=("html",)).get_content()
    assert SECURITY_NOTICE_TEXT in text
    assert "Security notice:" in html
    assert parsed["Subject"] == "Reset your password"
    assert "AAAA-BBBB-CCCC-DDDD-EEEE" in text
    assert "AAAA-BBBB-CCCC-DDDD-EEEE" in html


@pytest.mark.unit
def test_encrypted_message_hides_subject_and_wraps_complete_inner_mime():
    with patch("plane.mailer.mime.encrypt_for_certificate", return_value="ciphertext") as encrypt:
        message = build_encrypted_message(
            inner_subject="Confidential project title",
            text_body="Confidential body",
            html_body="<p>Confidential body</p>",
            sender="Hangar <hello@hangar.example.com>",
            recipient="person@example.com",
            message_id="<message@hangar.example.com>",
            certificate="public certificate",
            encryption_subkey_fingerprint="A" * 40,
            receipt_code="AAAA-BBBB-CCCC-DDDD-EEEE",
            attachments=[{"filename": "report.csv", "content": b"a,b\n1,2\n", "content_type": "text/csv"}],
        )

    assert message["Subject"] == "Encrypted Hangar notification"
    assert "Confidential" not in message.as_string()
    inner_bytes = encrypt.call_args.args[0]
    inner = BytesParser(policy=policy.default).parsebytes(inner_bytes)
    assert inner["Subject"] == "Confidential project title"
    assert inner.get_body(preferencelist=("plain",)).get_content().startswith("Confidential body")
    assert "AAAA-BBBB-CCCC-DDDD-EEEE" in inner.get_body(preferencelist=("plain",)).get_content()
    assert any(part.get_filename() == "report.csv" for part in inner.walk())


@pytest.mark.unit
def test_attachment_filename_is_reduced_to_basename():
    message = build_clear_message(
        subject="Export",
        text_body="Attached",
        html_body="",
        sender="Hangar <hello@hangar.example.com>",
        recipient="person@example.com",
        message_id="<message@hangar.example.com>",
        attachments=[{"filename": "../../report.csv", "content": b"x", "content_type": "text/csv"}],
    )

    assert any(part.get_filename() == "report.csv" for part in message.walk())


@pytest.mark.unit
def test_email_html_cannot_load_remote_resources():
    sanitized = sanitize_email_html(
        '<style>@import url("https://fonts.example/style.css")</style>'
        '<p style="background:url(https://tracker.example/pixel)">Update</p>'
        '<img src="https://tracker.example/pixel" alt="tracking image">'
        '<script>alert("unsafe")</script><a href="javascript:alert(1)" onclick="alert(2)">Unsafe</a>'
        '<a href="https://hangar.example.com/project">Open project</a>'
    )

    assert "tracker.example" not in sanitized
    assert "fonts.example" not in sanitized
    assert "javascript:" not in sanitized
    assert "onclick" not in sanitized
    assert "<script" not in sanitized
    assert "https://hangar.example.com/project" in sanitized
