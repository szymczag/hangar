# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Deterministic cleartext and RFC 3156 PGP/MIME construction."""

from email import policy
from email.message import EmailMessage
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate
from pathlib import PurePath
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .openpgp import encrypt_for_certificate

SECURITY_NOTICE_TEXT = (
    "Security notice: This message is unencrypted because it is required to access or secure your Hangar account. "
    "To receive project and activity notifications by email, add and verify an OpenPGP public key in Profile > "
    "Security. Until then, those notifications remain available only in Hangar."
)

SECURITY_NOTICE_HTML = (
    '<div role="note" style="border:1px solid #d1d5db;padding:12px;margin:0 0 16px">'
    "<strong>Security notice:</strong> This message is unencrypted because it is required to access or secure your "
    "Hangar account. To receive project and activity notifications by email, add and verify an OpenPGP public key "
    "in Profile &gt; Security. Until then, those notifications remain available only in Hangar.</div>"
)


def _append_receipt(text_body: str, html_body: str, receipt_code: str) -> tuple[str, str]:
    if not receipt_code:
        return text_body, html_body
    text_body = f"{text_body}\n\nHangar email receipt: {receipt_code}"
    if html_body:
        soup = BeautifulSoup(html_body, "html.parser")
        footer = BeautifulSoup(
            '<p style="border-top:1px solid #d1d5db;margin-top:20px;padding-top:12px">'
            f"Hangar email receipt: <strong>{receipt_code}</strong></p>",
            "html.parser",
        ).find("p")
        target = soup.body or soup
        if footer is not None:
            target.append(footer)
        html_body = str(soup)
    return text_body, html_body


def sanitize_email_html(html_body: str) -> str:
    """Remove resources that an email client could fetch when a message opens."""

    if not html_body:
        return ""
    soup = BeautifulSoup(html_body, "html.parser")
    for tag in soup.find_all(
        [
            "audio",
            "base",
            "button",
            "embed",
            "form",
            "iframe",
            "img",
            "input",
            "link",
            "math",
            "meta",
            "object",
            "script",
            "source",
            "svg",
            "video",
        ]
    ):
        tag.decompose()
    for tag in soup.find_all(True):
        for attribute in list(tag.attrs):
            lowered = attribute.lower()
            if lowered.startswith("on") or lowered in {"background", "formaction", "src", "srcset"}:
                del tag.attrs[attribute]
        style_value = str(tag.get("style", "")).lower()
        if "url(" in style_value or "expression(" in style_value:
            del tag["style"]
        if tag.has_attr("href"):
            parsed = urlparse(str(tag["href"]).strip())
            if parsed.scheme.lower() not in {"http", "https", "mailto"}:
                del tag["href"]
    for style in soup.find_all("style"):
        if "@import" in style.get_text().lower() or "url(" in style.get_text().lower():
            style.decompose()
    return str(soup)


def _prepend_security_notice(html_body: str) -> str:
    soup = BeautifulSoup(html_body, "html.parser")
    notice = BeautifulSoup(SECURITY_NOTICE_HTML, "html.parser").find("div")
    target = soup.body or soup
    if notice is not None:
        target.insert(0, notice)
    return str(soup)


def _set_common_headers(
    message: EmailMessage | MIMEMultipart,
    *,
    subject: str,
    sender: str,
    recipient: str,
    message_id: str,
    reply_to: str = "",
) -> None:
    if message.get("Subject") is None:
        message["Subject"] = subject
    else:
        message.replace_header("Subject", subject)
    message["From"] = sender
    message["To"] = recipient
    message["Message-ID"] = message_id
    message["Date"] = formatdate(localtime=False, usegmt=True)
    message["Auto-Submitted"] = "auto-generated"
    if reply_to:
        message["Reply-To"] = reply_to


def _inner_alternative(
    *, subject: str, text_body: str, html_body: str, attachments: list[dict[str, object]] | None = None
) -> EmailMessage:
    inner = EmailMessage(policy=policy.SMTP)
    inner["Subject"] = subject
    inner.set_content(text_body)
    if html_body:
        inner.add_alternative(html_body, subtype="html")
    for attachment in attachments or []:
        filename = PurePath(str(attachment["filename"])).name
        if not filename or any(character in filename for character in "\r\n"):
            raise ValueError("Invalid attachment filename")
        maintype, _, subtype = str(attachment["content_type"]).partition("/")
        if not maintype or not subtype:
            raise ValueError("Invalid attachment content type")
        content = attachment["content"]
        if not isinstance(content, bytes):
            raise ValueError("Invalid attachment content")
        inner.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    return inner


def build_clear_message(
    *,
    subject: str,
    text_body: str,
    html_body: str,
    sender: str,
    recipient: str,
    message_id: str,
    reply_to: str = "",
    include_security_notice: bool = False,
    receipt_code: str = "",
    attachments: list[dict[str, object]] | None = None,
) -> EmailMessage:
    if include_security_notice:
        text_body = f"{SECURITY_NOTICE_TEXT}\n\n{text_body}"
        html_body = _prepend_security_notice(html_body) if html_body else ""
    text_body, html_body = _append_receipt(text_body, html_body, receipt_code)
    message = _inner_alternative(subject=subject, text_body=text_body, html_body=html_body, attachments=attachments)
    _set_common_headers(
        message,
        subject=subject,
        sender=sender,
        recipient=recipient,
        message_id=message_id,
        reply_to=reply_to,
    )
    return message


def build_encrypted_message(
    *,
    inner_subject: str,
    text_body: str,
    html_body: str,
    sender: str,
    recipient: str,
    message_id: str,
    certificate: str,
    encryption_subkey_fingerprint: str,
    reply_to: str = "",
    receipt_code: str = "",
    attachments: list[dict[str, object]] | None = None,
) -> MIMEMultipart:
    text_body, html_body = _append_receipt(text_body, html_body, receipt_code)
    inner = _inner_alternative(
        subject=inner_subject,
        text_body=text_body,
        html_body=html_body,
        attachments=attachments,
    )
    ciphertext = encrypt_for_certificate(
        inner.as_bytes(policy=policy.SMTP),
        certificate,
        encryption_subkey_fingerprint,
    )

    outer = MIMEMultipart(_subtype="encrypted", protocol="application/pgp-encrypted")
    _set_common_headers(
        outer,
        subject="Encrypted Hangar notification",
        sender=sender,
        recipient=recipient,
        message_id=message_id,
        reply_to=reply_to,
    )

    version_part = MIMEBase("application", "pgp-encrypted")
    version_part.set_payload("Version: 1\r\n")
    version_part["Content-Transfer-Encoding"] = "7bit"
    outer.attach(version_part)

    encrypted_part = MIMEBase("application", "octet-stream", name="encrypted.asc")
    encrypted_part.set_payload(ciphertext)
    encrypted_part["Content-Transfer-Encoding"] = "7bit"
    encrypted_part["Content-Disposition"] = 'inline; filename="encrypted.asc"'
    outer.attach(encrypted_part)
    return outer
