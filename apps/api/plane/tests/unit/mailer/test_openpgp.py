import shutil
import subprocess

import pytest

from plane.mailer.exceptions import OpenPGPError
from plane.mailer.openpgp import MAX_CERTIFICATE_BYTES, encrypt_for_certificate, inspect_certificate


@pytest.mark.unit
def test_private_key_material_is_rejected_before_gnu_pg_runs():
    with pytest.raises(OpenPGPError, match="Private-key material"):
        inspect_certificate("-----BEGIN PGP PUBLIC KEY BLOCK-----\n-----BEGIN PGP PRIVATE KEY BLOCK-----\n")


@pytest.mark.unit
def test_oversized_certificate_is_rejected_before_gnu_pg_runs():
    certificate = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n" + ("A" * MAX_CERTIFICATE_BYTES)

    with pytest.raises(OpenPGPError, match="64 KiB"):
        inspect_certificate(certificate)


@pytest.mark.unit
def test_non_armored_input_is_rejected():
    with pytest.raises(OpenPGPError, match="ASCII-armored"):
        inspect_certificate("not a public certificate")


@pytest.mark.unit
def test_real_certificate_inspection_and_encryption_round_trip(tmp_path):
    if shutil.which("gpg") is None:
        pytest.skip("GnuPG is not installed in this test environment")
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    common = [
        "gpg",
        "--homedir",
        str(home),
        "--batch",
        "--pinentry-mode",
        "loopback",
        "--passphrase",
        "",
    ]
    generated = subprocess.run(
        [
            *common,
            "--quick-generate-key",
            "Hangar Test <mail-test@example.com>",
            "rsa3072",
            "cert,sign",
            "1d",
        ],
        check=False,
        capture_output=True,
        timeout=20,
    )
    assert generated.returncode == 0, generated.stderr.decode(errors="replace")

    listed = subprocess.run(
        [*common, "--with-colons", "--list-keys"],
        check=True,
        capture_output=True,
        timeout=10,
    )
    fingerprint = next(line.split(":")[9] for line in listed.stdout.decode().splitlines() if line.startswith("fpr:"))
    added = subprocess.run(
        [*common, "--quick-add-key", fingerprint, "rsa3072", "encrypt", "1d"],
        check=False,
        capture_output=True,
        timeout=20,
    )
    assert added.returncode == 0, added.stderr.decode(errors="replace")

    exported = subprocess.run(
        [*common, "--armor", "--export", fingerprint],
        check=True,
        capture_output=True,
        timeout=10,
    )
    certificate = exported.stdout.decode("ascii")
    info = inspect_certificate(certificate)
    assert info.primary_fingerprint == fingerprint
    assert info.encryption_algorithm == "RSA"
    assert info.encryption_key_size == 3072

    ciphertext = encrypt_for_certificate(b"confidential test message", certificate, info.encryption_subkey_fingerprint)
    decrypted = subprocess.run(
        [*common, "--decrypt"],
        input=ciphertext.encode("ascii"),
        check=True,
        capture_output=True,
        timeout=10,
    )
    assert decrypted.stdout == b"confidential test message"
