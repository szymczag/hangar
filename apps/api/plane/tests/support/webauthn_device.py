# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""A software security key, for testing the WebAuthn endpoints end to end.

Written here rather than pulled in: the published software authenticator
(soft-webauthn) depends on fido2, which pins cryptography below 40, while this
project runs 50 and py_webauthn requires 44 or newer. That conflict is
unresolvable, and the operations involved are small enough to implement against
the libraries already present.

It produces genuine ES256 signatures over genuine authenticator data, so
py_webauthn verifies them exactly as it would a hardware key's. What it cannot
tell us is whether a browser will agree to call navigator.credentials for a
given relying-party ID — that is a property of the browser and of DNS.
"""

import base64
import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

# Bit flags in authenticator data: user present, user verified, attested
# credential data included.
FLAG_UP = 0x01
FLAG_UV = 0x04
FLAG_AT = 0x40

COSE_ES256 = -7


def b64(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SoftwareAuthenticator:
    """One credential, held in memory."""

    def __init__(self, aaguid=b"\x00" * 16):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.aaguid = aaguid
        self.sign_count = 0

    # -- helpers -----------------------------------------------------------

    def _cose_key(self):
        numbers = self.private_key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,  # kty: EC2
                3: COSE_ES256,
                -1: 1,  # crv: P-256
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def _client_data(self, kind, challenge, origin):
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": origin, "crossOrigin": False},
            separators=(",", ":"),
        ).encode()

    def _authenticator_data(self, rp_id, flags, include_credential):
        data = hashlib.sha256(rp_id.encode()).digest() + struct.pack(">BI", flags, self.sign_count)
        if include_credential:
            data += self.aaguid + struct.pack(">H", len(self.credential_id)) + self.credential_id + self._cose_key()
        return data

    # -- the two operations a browser performs -----------------------------

    def create(self, *, rp_id, challenge, origin):
        """Answer navigator.credentials.create()."""
        client_data = self._client_data("webauthn.create", challenge, origin)
        auth_data = self._authenticator_data(rp_id, FLAG_UP | FLAG_UV | FLAG_AT, include_credential=True)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64(client_data),
                "attestationObject": b64(attestation),
                "transports": ["usb"],
            },
        }

    def get(self, *, rp_id, challenge, origin, sign_count=None):
        """Answer navigator.credentials.get().

        ``sign_count`` overrides the counter, which is how a cloned
        authenticator is simulated: a copy still holds an older value.
        """
        if sign_count is None:
            self.sign_count += 1
        else:
            self.sign_count = sign_count

        client_data = self._client_data("webauthn.get", challenge, origin)
        auth_data = self._authenticator_data(rp_id, FLAG_UP | FLAG_UV, include_credential=False)
        signature = self.private_key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64(client_data),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
                "userHandle": None,
            },
        }


__all__ = ["SoftwareAuthenticator", "b64", "unb64"]
