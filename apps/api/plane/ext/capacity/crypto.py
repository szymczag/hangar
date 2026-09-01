import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _fernets():
    if not settings.CALENDAR_TOKEN_ENCRYPTION_KEYS:
        raise ImproperlyConfigured("Calendar token encryption is not configured")
    try:
        return [
            (hashlib.sha256(key.encode()).hexdigest(), Fernet(key.encode()))
            for key in settings.CALENDAR_TOKEN_ENCRYPTION_KEYS
        ]
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("CALENDAR_TOKEN_ENCRYPTION_KEYS contains an invalid Fernet key") from exc


def encrypt_value(value: str) -> tuple[str, str]:
    if not value:
        raise ValueError("A non-empty value is required")
    key_id, cipher = _fernets()[0]
    return cipher.encrypt(value.encode()).decode(), key_id


def decrypt_value(value: str, key_id: str = "") -> str:
    if not value:
        raise ValueError("Encrypted value is missing")
    candidates = _fernets()
    if key_id:
        candidates.sort(key=lambda item: item[0] != key_id)
    for _, cipher in candidates:
        try:
            return cipher.decrypt(value.encode()).decode()
        except InvalidToken:
            continue
    raise ValueError("Encrypted calendar credential cannot be decrypted")
