# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Constrained GnuPG adapter for public-certificate validation and encryption."""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings

from .exceptions import OpenPGPError

MAX_CERTIFICATE_BYTES = 64 * 1024
MAX_UIDS = 32
MAX_SUBKEYS = 16
MAX_SIGNATURES = 256
GPG_TIMEOUT_SECONDS = 10
_FINGERPRINT_RE = re.compile(r"^[A-F0-9]{40,64}$")


@dataclass(frozen=True)
class OpenPGPCertificateInfo:
    normalized_certificate: str
    primary_fingerprint: str
    encryption_subkey_fingerprint: str
    primary_algorithm: str
    encryption_algorithm: str
    encryption_key_size: int | None
    created_at: datetime | None
    expires_at: datetime | None


def _gpg_binary() -> str:
    return getattr(settings, "EMAIL_GPG_BINARY", "gpg")


def _environment(home: str) -> dict[str, str]:
    return {
        "GNUPGHOME": home,
        "HOME": home,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }


def _run_gpg(home: str, arguments: list[str], *, input_data: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    command = [
        _gpg_binary(),
        "--no-options",
        "--batch",
        "--no-tty",
        "--homedir",
        home,
        "--auto-key-locate",
        "clear",
        "--no-auto-key-retrieve",
        "--no-autostart",
        *arguments,
    ]
    try:
        return subprocess.run(
            command,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=GPG_TIMEOUT_SECONDS,
            env=_environment(home),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OpenPGPError("OpenPGP processing failed safely") from exc


def _timestamp(value: str) -> datetime | None:
    if not value or value == "0":
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


def _algorithm_name(algorithm: str) -> str:
    return {
        "1": "RSA",
        "2": "RSA Encrypt-Only",
        "3": "RSA Sign-Only",
        "16": "ElGamal",
        "17": "DSA",
        "18": "ECDH",
        "19": "ECDSA",
        "22": "EdDSA",
    }.get(algorithm, f"OpenPGP algorithm {algorithm}")


def _validate_encryption_algorithm(algorithm: str, bits: int | None) -> None:
    if algorithm in {"1", "2"} and bits is not None and bits >= 3072:
        return
    if algorithm == "18" and bits is not None and bits >= 255:
        return
    raise OpenPGPError("The certificate has no supported strong encryption subkey")


def inspect_certificate(certificate: str) -> OpenPGPCertificateInfo:
    encoded = certificate.encode("utf-8")
    if not encoded or len(encoded) > MAX_CERTIFICATE_BYTES:
        raise OpenPGPError("The public certificate must be between 1 byte and 64 KiB")
    if "-----BEGIN PGP PUBLIC KEY BLOCK-----" not in certificate:
        raise OpenPGPError("Upload an ASCII-armored OpenPGP public certificate")
    if "PRIVATE KEY BLOCK" in certificate:
        raise OpenPGPError("Private-key material is not accepted")

    with tempfile.TemporaryDirectory(prefix="hangar-openpgp-") as home:
        Path(home).chmod(0o700)
        shown = _run_gpg(
            home,
            ["--with-colons", "--import-options", "show-only", "--import"],
            input_data=encoded,
        )
        if shown.returncode != 0:
            raise OpenPGPError("The public certificate is malformed")

        records = [line.split(":") for line in shown.stdout.decode("utf-8", errors="replace").splitlines()]
        public_records = [record for record in records if record and record[0] == "pub"]
        if len(public_records) != 1:
            raise OpenPGPError("Upload exactly one OpenPGP public certificate")
        if sum(1 for record in records if record and record[0] == "uid") > MAX_UIDS:
            raise OpenPGPError("The certificate contains too many user IDs")
        if sum(1 for record in records if record and record[0] == "sub") > MAX_SUBKEYS:
            raise OpenPGPError("The certificate contains too many subkeys")
        if sum(1 for record in records if record and record[0] == "sig") > MAX_SIGNATURES:
            raise OpenPGPError("The certificate contains too many signatures")

        primary = public_records[0]
        if len(primary) < 12 or primary[1] in {"r", "e", "d"}:
            raise OpenPGPError("The primary OpenPGP key is revoked, expired, or disabled")
        primary_expires_at = _timestamp(primary[6])
        if primary_expires_at is not None and primary_expires_at <= datetime.now(tz=UTC):
            raise OpenPGPError("The primary OpenPGP key is expired")

        primary_fingerprint = ""
        encryption_candidates: list[tuple[list[str], str]] = []
        current_key_record: list[str] | None = None
        for record in records:
            if not record:
                continue
            if record[0] in {"pub", "sub"}:
                current_key_record = record
            elif record[0] == "fpr" and len(record) > 9:
                fingerprint = record[9].upper()
                if not _FINGERPRINT_RE.fullmatch(fingerprint):
                    raise OpenPGPError("The certificate contains an invalid fingerprint")
                if current_key_record is None:
                    continue
                if current_key_record[0] == "pub" and not primary_fingerprint:
                    primary_fingerprint = fingerprint
                if len(current_key_record) >= 12:
                    capabilities = current_key_record[11].lower()
                    validity = current_key_record[1]
                    expires_at = _timestamp(current_key_record[6])
                    if (
                        "e" in capabilities
                        and validity not in {"r", "e", "d"}
                        and (expires_at is None or expires_at > datetime.now(tz=UTC))
                    ):
                        encryption_candidates.append((current_key_record, fingerprint))

        selected = max(
            encryption_candidates,
            key=lambda candidate: (
                candidate[0][0] == "sub",
                int(candidate[0][5]) if candidate[0][5].isdigit() else 0,
                int(candidate[0][6]) if candidate[0][6].isdigit() else 2**63 - 1,
            ),
            default=None,
        )
        if not primary_fingerprint or selected is None:
            raise OpenPGPError("The certificate has no currently valid encryption key")
        selected_subkey, selected_subkey_fingerprint = selected

        bits = int(selected_subkey[2]) if selected_subkey[2].isdigit() else None
        algorithm = selected_subkey[3]
        _validate_encryption_algorithm(algorithm, bits)

        imported = _run_gpg(home, ["--import-options", "import-minimal", "--import"], input_data=encoded)
        if imported.returncode != 0:
            raise OpenPGPError("The public certificate could not be imported")
        exported = _run_gpg(home, ["--armor", "--export", primary_fingerprint])
        if exported.returncode != 0 or not exported.stdout:
            raise OpenPGPError("The public certificate could not be normalized")

        selected_expires_at = _timestamp(selected_subkey[6])
        effective_expiry = min(
            (value for value in (primary_expires_at, selected_expires_at) if value is not None),
            default=None,
        )
        return OpenPGPCertificateInfo(
            normalized_certificate=exported.stdout.decode("ascii"),
            primary_fingerprint=primary_fingerprint,
            encryption_subkey_fingerprint=selected_subkey_fingerprint,
            primary_algorithm=_algorithm_name(primary[3]),
            encryption_algorithm=_algorithm_name(algorithm),
            encryption_key_size=bits,
            created_at=_timestamp(selected_subkey[5]),
            expires_at=effective_expiry,
        )


def encrypt_for_certificate(plaintext: bytes, certificate: str, encryption_subkey_fingerprint: str) -> str:
    if len(plaintext) > getattr(settings, "EMAIL_MAX_STORED_PAYLOAD_BYTES", 262144) * 2:
        raise OpenPGPError("The message is too large for encrypted email delivery")
    if not _FINGERPRINT_RE.fullmatch(encryption_subkey_fingerprint.upper()):
        raise OpenPGPError("The selected encryption fingerprint is invalid")

    encoded_certificate = certificate.encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="hangar-openpgp-") as home:
        Path(home).chmod(0o700)
        imported = _run_gpg(home, ["--import-options", "import-minimal", "--import"], input_data=encoded_certificate)
        if imported.returncode != 0:
            raise OpenPGPError("The public certificate could not be imported")
        encrypted = _run_gpg(
            home,
            [
                "--armor",
                "--trust-model",
                "always",
                "--recipient",
                f"{encryption_subkey_fingerprint}!",
                "--encrypt",
            ],
            input_data=plaintext,
        )
        if encrypted.returncode != 0 or not encrypted.stdout:
            raise OpenPGPError("The message could not be encrypted to the selected key")
        return encrypted.stdout.decode("ascii")
