"""Authenticated SMTP transport with explicit failure classification."""

import smtplib
import ssl
import re
from email.message import Message

from django.conf import settings

from plane.license.utils.instance_value import get_email_configuration

from ..exceptions import (
    MailAcceptanceUnknownError,
    MailConfigurationError,
    MailPermanentError,
    MailRetryableError,
)
from .base import TransportReceipt


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
            if ssl_enabled:
                client = smtplib.SMTP_SSL(
                    host=host,
                    port=int(port),
                    timeout=timeout,
                    context=ssl.create_default_context(),
                )
            else:
                client = smtplib.SMTP(host=host, port=int(port), timeout=timeout)
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
