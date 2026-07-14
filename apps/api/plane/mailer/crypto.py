"""Versioned authenticated encryption for short-lived mailer data."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import uuid
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from .exceptions import MailConfigurationError


def _configured_keys() -> dict[str, bytes]:
    raw_keys = getattr(settings, "EMAIL_OUTBOX_ENCRYPTION_KEYS", "")
    keys: dict[str, bytes] = {}
    for item in filter(None, (part.strip() for part in raw_keys.split(","))):
        try:
            version, encoded = item.split(":", 1)
            key = base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
            raise MailConfigurationError("EMAIL_OUTBOX_ENCRYPTION_KEYS has an invalid entry") from exc
        if not version or len(key) != 32:
            raise MailConfigurationError("Email encryption keys must have a version and decode to 32 bytes")
        keys[version] = key
    if not keys:
        raise MailConfigurationError("EMAIL_OUTBOX_ENCRYPTION_KEYS is required for secure email storage")
    return keys


def encrypt_bytes(value: bytes, *, associated_data: bytes) -> str:
    keys = _configured_keys()
    version = next(iter(keys))
    nonce = os.urandom(12)
    ciphertext = AESGCM(keys[version]).encrypt(nonce, value, associated_data)
    return ".".join(
        (
            version,
            base64.urlsafe_b64encode(nonce).decode("ascii"),
            base64.urlsafe_b64encode(ciphertext).decode("ascii"),
        )
    )


def decrypt_bytes(value: str, *, associated_data: bytes) -> bytes:
    try:
        version, encoded_nonce, encoded_ciphertext = value.split(".", 2)
        keys = _configured_keys()
        key = keys[version]
        nonce = base64.urlsafe_b64decode(encoded_nonce.encode("ascii"))
        ciphertext = base64.urlsafe_b64decode(encoded_ciphertext.encode("ascii"))
    except (ValueError, KeyError, UnicodeEncodeError) as exc:
        raise MailConfigurationError("Encrypted email data is malformed or uses an unknown key version") from exc
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, associated_data)
    except Exception as exc:
        raise MailConfigurationError("Encrypted email data failed authentication") from exc


def encrypt_json(value: Mapping, *, associated_data: bytes) -> str:
    serialized = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return encrypt_bytes(serialized, associated_data=associated_data)


def decrypt_json(value: str, *, associated_data: bytes) -> dict:
    decoded = json.loads(decrypt_bytes(value, associated_data=associated_data))
    if not isinstance(decoded, dict):
        raise MailConfigurationError("Encrypted email payload is not an object")
    return decoded


def keyed_digest(value: str, *, purpose: str) -> str:
    """Return a stable, non-reversible lookup for normalized sensitive data."""

    raw_key = getattr(settings, "EMAIL_LOOKUP_HMAC_KEY", "")
    try:
        key = base64.b64decode(raw_key.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise MailConfigurationError("EMAIL_LOOKUP_HMAC_KEY is malformed") from exc
    if len(key) != 32:
        raise MailConfigurationError("EMAIL_LOOKUP_HMAC_KEY must decode to 32 bytes")
    return hmac.new(key, f"{purpose}\0{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def email_receipt_code(outbox_id: uuid.UUID) -> str:
    """Return a user-comparable code without exposing an internal outbox identifier."""

    digest = keyed_digest(str(outbox_id), purpose="email-receipt").upper()[:20]
    return "-".join(digest[index : index + 4] for index in range(0, len(digest), 4))
