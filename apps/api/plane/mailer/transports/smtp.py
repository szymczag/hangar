# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Authenticated SMTP transport with explicit failure classification."""

import ipaddress
import re
import smtplib
import socket
import ssl
from email.message import Message

from django.conf import settings

from plane.license.utils.instance_value import get_email_configuration
from plane.utils.ip_address import resolve_and_validate

from ..exceptions import (
    MailAcceptanceUnknownError,
    MailConfigurationError,
    MailPermanentError,
    MailRetryableError,
)
from .base import TransportReceipt


def _connect_pinned(addresses, port, timeout):
    last_error = None
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        family = socket.AF_INET6 if parsed.version == 6 else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sockaddr = (str(parsed), port, 0, 0) if parsed.version == 6 else (str(parsed), port)
            sock.connect(sockaddr)
            peer = ipaddress.ip_address(sock.getpeername()[0].split("%", 1)[0])
            if peer != parsed:
                raise OSError("SMTP connection peer does not match the validated address")
            return sock
        except OSError as exc:
            last_error = exc
            sock.close()
    raise OSError("Unable to connect to the validated SMTP destination") from last_error


class _PinnedSMTP(smtplib.SMTP):
    def __init__(self, host, port, *, addresses, timeout):
        self._pinned_addresses = addresses
        super().__init__(host=host, port=port, timeout=timeout)

    def _get_socket(self, host, port, timeout):
        return _connect_pinned(self._pinned_addresses, port, timeout)


class _PinnedSMTPSSL(smtplib.SMTP_SSL):
    def __init__(self, host, port, *, addresses, timeout, context):
        self._pinned_addresses = addresses
        super().__init__(host=host, port=port, timeout=timeout, context=context)

    def _get_socket(self, host, port, timeout):
        raw_socket = _connect_pinned(self._pinned_addresses, port, timeout)
        try:
            return self.context.wrap_socket(raw_socket, server_hostname=host)
        except Exception:
            raw_socket.close()
            raise


def _smtp_client(host, port, *, timeout, ssl_enabled):
    normalized_host = host.strip().rstrip(".").lower()
    if (
        not normalized_host
        or any(character in normalized_host for character in ("/", "\\", "@"))
        or any(ord(character) < 0x20 for character in normalized_host)
    ):
        raise MailConfigurationError("SMTP host is invalid")
    if port not in settings.SMTP_ALLOWED_PORTS:
        raise MailConfigurationError("SMTP port is not allowed by deployment policy")

    trusted_host = normalized_host in settings.SMTP_ALLOWED_HOSTS
    try:
        addresses = resolve_and_validate(
            normalized_host,
            allowed_ips=settings.SMTP_ALLOWED_IPS,
            require_safe=not trusted_host,
        )
    except ValueError as exc:
        raise MailConfigurationError("SMTP destination is not allowed by deployment policy") from exc

    if ssl_enabled:
        return _PinnedSMTPSSL(
            normalized_host,
            port,
            addresses=addresses,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    return _PinnedSMTP(normalized_host, port, addresses=addresses, timeout=timeout)


class SMTPTransport:
    def send(
        self,
        message: Message,
        *,
        configuration_set: str = "",
        message_tags: dict[str, str] | None = None,
    ) -> TransportReceipt:
        host, username, password, port, use_tls, use_ssl, _sender = get_email_configuration()
        if not host:
            raise MailConfigurationError("SMTP host is not configured")
        tls_enabled = use_tls == "1"
        ssl_enabled = use_ssl == "1"
        if tls_enabled and ssl_enabled:
            raise MailConfigurationError("SMTP TLS and implicit SSL cannot both be enabled")
        if (username or password) and not (tls_enabled or ssl_enabled):
            raise MailConfigurationError("SMTP credentials require TLS")
        is_ses_smtp = getattr(settings, "EMAIL_PROVIDER", "smtp") in {"ses", "ses_smtp"}
        if is_ses_smtp and not tls_enabled:
            raise MailConfigurationError("Amazon SES SMTP requires STARTTLS in this deployment")

        if configuration_set and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", configuration_set):
            raise MailConfigurationError("The SES configuration set name is invalid")
        for key, value in (message_tags or {}).items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", key) or not re.fullmatch(r"[A-Za-z0-9_.@:/+-]{1,256}", value):
                raise MailConfigurationError("An SES message tag is invalid")
        if is_ses_smtp and configuration_set:
            message["X-SES-CONFIGURATION-SET"] = configuration_set
        if is_ses_smtp and message_tags:
            message["X-SES-MESSAGE-TAGS"] = ",".join(f"{key}={value}" for key, value in message_tags.items())

        stage = "connect"
        client: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        try:
            timeout = getattr(settings, "EMAIL_SMTP_TIMEOUT_SECONDS", 15)
            client = _smtp_client(
                host,
                int(port),
                timeout=timeout,
                ssl_enabled=ssl_enabled,
            )
            if not ssl_enabled:
                client.ehlo()
                if tls_enabled:
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
            if username:
                client.login(username, password or "")
            stage = "submit"
            refused = client.send_message(message)
            if refused:
                raise MailPermanentError("One or more SMTP recipients were refused")
            stage = "accepted"
            return TransportReceipt()
        except smtplib.SMTPAuthenticationError as exc:
            raise MailPermanentError("SMTP authentication failed") from exc
        except (smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused) as exc:
            raise MailPermanentError("SMTP sender or recipient was refused") from exc
        except smtplib.SMTPDataError as exc:
            if 400 <= exc.smtp_code < 500:
                raise MailRetryableError(f"SMTP temporary data failure ({exc.smtp_code})") from exc
            raise MailPermanentError(f"SMTP permanent data failure ({exc.smtp_code})") from exc
        except smtplib.SMTPResponseException as exc:
            if 400 <= exc.smtp_code < 500:
                raise MailRetryableError(f"SMTP temporary failure ({exc.smtp_code})") from exc
            raise MailPermanentError(f"SMTP permanent failure ({exc.smtp_code})") from exc
        except smtplib.SMTPServerDisconnected as exc:
            if stage == "submit":
                raise MailAcceptanceUnknownError("SMTP disconnected while message acceptance was unknown") from exc
            raise MailRetryableError("SMTP server disconnected before message submission") from exc
        except (OSError, TimeoutError, smtplib.SMTPException) as exc:
            if stage == "submit":
                raise MailAcceptanceUnknownError("SMTP submission ended without a definitive response") from exc
            raise MailRetryableError("SMTP connection failed before message submission") from exc
        finally:
            if client is not None and stage != "connect":
                try:
                    client.quit()
                except (OSError, smtplib.SMTPException):
                    pass
