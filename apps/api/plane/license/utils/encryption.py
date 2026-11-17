# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import base64
import hashlib
from functools import lru_cache
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

from plane.utils.exception_logger import log_exception


def derive_key(secret_key):
    # Use a key derivation function to get a suitable encryption key
    dk = hashlib.pbkdf2_hmac("sha256", secret_key.encode(), b"salt", 100000)
    return base64.urlsafe_b64encode(dk)


# Encrypt data
def encrypt_data(data):
    try:
        if data:
            cipher_suite = Fernet(derive_key(settings.SECRET_KEY))
            encrypted_data = cipher_suite.encrypt(data.encode())
            return encrypted_data.decode()  # Convert bytes to string
        else:
            return ""
    except Exception as e:
        log_exception(e)
        return ""


# Decrypt data
def decrypt_data(encrypted_data):
    try:
        if encrypted_data:
            cipher_suite = Fernet(derive_key(settings.SECRET_KEY))
            decrypted_data = cipher_suite.decrypt(encrypted_data.encode())  # Convert string back to bytes
            return decrypted_data.decode()
        else:
            return ""
    except Exception as e:
        log_exception(e)
        return ""


@lru_cache(maxsize=8)
def _cipher(secret_key):
    # derive_key runs 100,000 PBKDF2 rounds; configure_instance checks every
    # encrypted row against the same few keys.
    return Fernet(derive_key(secret_key))


def reencrypt_from_legacy_key(encrypted_data, legacy_keys=None):
    """Re-encrypt a value written under a published template SECRET_KEY.

    The installers replace a template SECRET_KEY with a random one. Values saved
    in God Mode before that (SMTP password, OAuth client secrets) were encrypted
    under the template key and would otherwise decrypt to nothing. Trying the
    template keys exposes nothing: they are public, so these values were never
    protected by them.

    Returns the value encrypted under the current SECRET_KEY, or None when the
    current key already opens it or no legacy key does.
    """
    if not encrypted_data:
        return None
    token = encrypted_data.encode()
    current = _cipher(settings.SECRET_KEY)
    try:
        current.decrypt(token)
        return None
    except InvalidToken:
        pass
    if legacy_keys is None:
        legacy_keys = getattr(settings, "LEGACY_SECRET_KEYS", ())
    for legacy_key in legacy_keys:
        if legacy_key == settings.SECRET_KEY:
            continue
        try:
            plaintext = _cipher(legacy_key).decrypt(token)
        except InvalidToken:
            continue
        return current.encrypt(plaintext).decode()
    return None
