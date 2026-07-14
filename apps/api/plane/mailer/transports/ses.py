"""Amazon SES v2 raw-message transport over HTTPS."""

import re
from email import policy
from email.message import Message
from email.utils import parseaddr

import boto3
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from django.conf import settings

from ..exceptions import (
    MailAcceptanceUnknownError,
    MailConfigurationError,
    MailPermanentError,
    MailRetryableError,
)
from .base import TransportReceipt

_PERMANENT_CODES = {
    "BadRequestException",
    "MailFromDomainNotVerifiedException",
    "MessageRejected",
    "NotFoundException",
}
_RETRYABLE_CODES = {
    "AccountSuspendedException",
    "LimitExceededException",
    "TooManyRequestsException",
}
_CONFIGURATION_SET_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_TAG_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def _client():
    kwargs = {"region_name": settings.EMAIL_SES_REGION}
    if settings.EMAIL_SES_AWS_ACCESS_KEY_ID:
        kwargs.update(
            {
                "aws_access_key_id": settings.EMAIL_SES_AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": settings.EMAIL_SES_AWS_SECRET_ACCESS_KEY,
                "aws_session_token": settings.EMAIL_SES_AWS_SESSION_TOKEN or None,
            }
        )
    return boto3.client("sesv2", **kwargs)


class SESAPITransport:
    def send(
        self,
        message: Message,
        *,
        configuration_set: str = "",
        message_tags: dict[str, str] | None = None,
    ) -> TransportReceipt:
        sender = parseaddr(str(message.get("From", "")))[1]
        recipient = parseaddr(str(message.get("To", "")))[1]
        if not sender or not recipient:
            raise MailConfigurationError("SES API delivery requires valid From and To addresses")
        if configuration_set and not _CONFIGURATION_SET_RE.fullmatch(configuration_set):
            raise MailConfigurationError("The SES configuration set name is invalid")
        if len(message_tags or {}) > 50 or any(
            not _TAG_RE.fullmatch(key) or not _TAG_RE.fullmatch(value) for key, value in (message_tags or {}).items()
        ):
            raise MailConfigurationError("An SES message tag is invalid")

        request = {
            "FromEmailAddress": sender,
            "Destination": {"ToAddresses": [recipient]},
            "Content": {"Raw": {"Data": message.as_bytes(policy=policy.SMTP)}},
        }
        if configuration_set:
            request["ConfigurationSetName"] = configuration_set
        if message_tags:
            request["EmailTags"] = [{"Name": key, "Value": value} for key, value in message_tags.items()]

        try:
            response = _client().send_email(**request)
        except ReadTimeoutError as exc:
            raise MailAcceptanceUnknownError("SES API response was lost after request submission") from exc
        except (ConnectTimeoutError, ConnectionClosedError, EndpointConnectionError) as exc:
            raise MailRetryableError("SES API endpoint was unavailable before submission") from exc
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = str(error.get("Code", "SESClientError"))
            http_status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
            if code in _RETRYABLE_CODES or http_status >= 500:
                raise MailRetryableError(f"SES API temporary failure ({code})") from exc
            if code in _PERMANENT_CODES or 400 <= http_status < 500:
                raise MailPermanentError(f"SES API rejected the message ({code})") from exc
            raise MailRetryableError(f"SES API request failed ({code})") from exc

        message_id = str(response.get("MessageId", ""))
        if not message_id:
            raise MailAcceptanceUnknownError("SES API accepted the request without returning a message identifier")
        return TransportReceipt(provider_message_id=message_id)
