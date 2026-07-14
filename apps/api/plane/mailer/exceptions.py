"""Typed failures used to make delivery retry behavior explicit."""


class MailerError(Exception):
    """Base error for outbound mail."""


class MailConfigurationError(MailerError):
    """Required secure mail configuration is missing or invalid."""


class MailPolicyError(MailerError):
    """A producer attempted an operation forbidden by policy."""


class MailRetryableError(MailerError):
    """The message can be retried safely after backoff."""


class MailPermanentError(MailerError):
    """The message cannot succeed until input or configuration changes."""


class MailAcceptanceUnknownError(MailerError):
    """The transport disconnected after submission may have been accepted."""


class OpenPGPError(MailerError):
    """The supplied certificate or encryption operation is invalid."""
