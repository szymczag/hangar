# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The installers must not leave the bundled object storage on the template login.

The proxy serves the object storage's S3 API on the application's origin, so the
`access-key` / `secret-key` pair the templates used to ship let anybody sign
requests against every upload. `install.sh` (Compose) and `swarm.sh` (Swarm)
replace that pair on install and upgrade. These tests run the real function from
each script against a scratch `plane.env`.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = (
    REPOSITORY_ROOT / "deployments" / "cli" / "community" / "install.sh",
    REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh",
)
VARIABLES_PATH = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "variables.env"
MIGRATE_PATH = (
    REPOSITORY_ROOT / "deployments" / "cli" / "community" / "migrate-object-storage.sh"
)
BUNDLED = "http://plane-minio:9000"


def _functions(script: Path) -> str:
    """The helper functions the rotation needs, cut out of the script."""
    source = script.read_text()
    parts = []
    for name in ("getEnvValue", "updateEnvFile", "generateStorageCredentials"):
        match = re.search(
            rf"^function {name}\(\)\{{?.*?^}}$", source, re.DOTALL | re.MULTILINE
        )
        if match is None:
            raise AssertionError(f"{script.name} has no {name}()")
        parts.append(match.group(0))
    return "OS_NAME=Linux\n" + "\n".join(parts)


def _env(path: Path) -> dict:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


class ObjectStorageCredentialRotationTests(unittest.TestCase):
    def _rotate(self, script: Path, lines: list, runs: int = 1) -> dict:
        with tempfile.TemporaryDirectory() as scratch:
            env_path = Path(scratch) / "plane.env"
            env_path.write_text("\n".join(lines) + "\n")
            program = _functions(script) + "\n" + "generateStorageCredentials\n" * runs
            subprocess.run(
                ["bash", "-c", program],
                check=True,
                capture_output=True,
                env={"DOCKER_ENV_PATH": str(env_path), "PATH": "/usr/bin:/bin"},
            )
            return _env(env_path)

    def test_a_fresh_install_gets_a_random_pair(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                first = self._rotate(
                    script,
                    [
                        "USE_MINIO=1",
                        "AWS_ACCESS_KEY_ID=",
                        "AWS_SECRET_ACCESS_KEY=",
                        f"AWS_S3_ENDPOINT_URL={BUNDLED}",
                    ],
                )
                second = self._rotate(
                    script,
                    [
                        "USE_MINIO=1",
                        "AWS_ACCESS_KEY_ID=",
                        "AWS_SECRET_ACCESS_KEY=",
                        f"AWS_S3_ENDPOINT_URL={BUNDLED}",
                    ],
                )
                self.assertRegex(first["AWS_ACCESS_KEY_ID"], r"^[A-Za-z0-9]{20}$")
                self.assertRegex(first["AWS_SECRET_ACCESS_KEY"], r"^[A-Za-z0-9]{40}$")
                self.assertNotEqual(
                    first["AWS_SECRET_ACCESS_KEY"], second["AWS_SECRET_ACCESS_KEY"]
                )

    def test_the_template_pair_is_replaced_and_kept_for_the_legacy_volume(self):
        for script in SCRIPTS:
            for access, secret in (
                ("access-key", "secret-key"),
                ('"access-key"', '"secret-key"'),
                ("custom", "secret-key"),
            ):
                with self.subTest(script=script.name, access=access, secret=secret):
                    env = self._rotate(
                        script,
                        [
                            "USE_MINIO=1",
                            f"AWS_ACCESS_KEY_ID={access}",
                            f"AWS_SECRET_ACCESS_KEY={secret}",
                            f"AWS_S3_ENDPOINT_URL={BUNDLED}",
                        ],
                    )
                    self.assertNotIn("secret-key", env["AWS_SECRET_ACCESS_KEY"])
                    self.assertRegex(env["AWS_SECRET_ACCESS_KEY"], r"^[A-Za-z0-9]{40}$")
                    self.assertEqual(env["LEGACY_MINIO_ROOT_USER"], access.strip('"'))
                    self.assertEqual(env["LEGACY_MINIO_ROOT_PASSWORD"], "secret-key")

    def test_a_second_run_keeps_the_generated_pair(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                lines = [
                    "USE_MINIO=1",
                    "AWS_ACCESS_KEY_ID=access-key",
                    "AWS_SECRET_ACCESS_KEY=secret-key",
                    f"AWS_S3_ENDPOINT_URL={BUNDLED}",
                ]
                with tempfile.TemporaryDirectory() as scratch:
                    env_path = Path(scratch) / "plane.env"
                    env_path.write_text("\n".join(lines) + "\n")
                    run = [
                        "bash",
                        "-c",
                        _functions(script) + "\ngenerateStorageCredentials\n",
                    ]
                    environment = {
                        "DOCKER_ENV_PATH": str(env_path),
                        "PATH": "/usr/bin:/bin",
                    }
                    subprocess.run(
                        run, check=True, capture_output=True, env=environment
                    )
                    first = env_path.read_text()
                    subprocess.run(
                        run, check=True, capture_output=True, env=environment
                    )
                    self.assertEqual(first, env_path.read_text())

    def test_an_operator_pair_and_external_storage_are_left_alone(self):
        cases = (
            [
                "USE_MINIO=1",
                "AWS_ACCESS_KEY_ID=me",
                "AWS_SECRET_ACCESS_KEY=SuperSecret123",
                f"AWS_S3_ENDPOINT_URL={BUNDLED}",
            ],
            [
                "USE_MINIO=0",
                "AWS_ACCESS_KEY_ID=access-key",
                "AWS_SECRET_ACCESS_KEY=secret-key",
                "AWS_S3_ENDPOINT_URL=https://s3.example.com",
            ],
            [
                "USE_MINIO=1",
                "AWS_ACCESS_KEY_ID=access-key",
                "AWS_SECRET_ACCESS_KEY=secret-key",
                "AWS_S3_ENDPOINT_URL=https://s3.example.com",
            ],
        )
        for script in SCRIPTS:
            for lines in cases:
                with self.subTest(script=script.name, lines=lines):
                    env = self._rotate(script, lines)
                    expected = dict(line.split("=", 1) for line in lines)
                    self.assertEqual(env, expected)

    def test_both_installers_run_it_after_syncing_the_env_file(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertRegex(
                    script.read_text(),
                    r"\n    syncEnvFile\n    generateStorageCredentials\n",
                )

    def test_the_template_ships_no_usable_pair_and_keeps_the_legacy_keys(self):
        env = _env(VARIABLES_PATH)
        self.assertEqual(env["AWS_ACCESS_KEY_ID"], "")
        self.assertEqual(env["AWS_SECRET_ACCESS_KEY"], "")
        # syncEnvFile carries over only keys the new template lists.
        self.assertIn("LEGACY_MINIO_ROOT_USER", env)
        self.assertIn("LEGACY_MINIO_ROOT_PASSWORD", env)

    def test_the_storage_migration_reads_the_legacy_volume_with_the_old_pair(self):
        source = MIGRATE_PATH.read_text()
        self.assertIn(
            '-e MINIO_ROOT_USER="$LEGACY_ACCESS_KEY" -e MINIO_ROOT_PASSWORD="$LEGACY_SECRET_KEY"',
            source,
        )
        self.assertIn('RCLONE_CONFIG_SRC_ACCESS_KEY_ID="$LEGACY_ACCESS_KEY"', source)
        self.assertIn('RCLONE_CONFIG_DST_ACCESS_KEY_ID="$ACCESS_KEY"', source)


if __name__ == "__main__":
    unittest.main()
