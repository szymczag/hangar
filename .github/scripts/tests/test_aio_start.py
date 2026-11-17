# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The all-in-one image's entrypoint must start with the volumes it documents.

A host directory mounted at /app/logs hides the log directories baked into the
image, and supervisord refuses to start when a log file's directory is missing,
so start.sh recreates them on every boot (upstream makeplane/plane#9818).

The secrets the container generates on first boot are kept on the data volume
(/app/data), not in the container layer: a container recreated from a new image
kept the image's template plane.env and generated a new SECRET_KEY, signing
everybody out and making saved instance settings unreadable (upstream
makeplane/plane#9987, adapted). The tests run start.sh's own functions against a
temporary plane.env and data directory.
"""

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
AIO = REPOSITORY_ROOT / "deployments" / "aio" / "community"
START = AIO / "start.sh"
SUPERVISOR = AIO / "supervisor.conf"


def _shell_function(source: str, name: str) -> str:
    match = re.search(rf"^{name}\(\)\s*\{{.*?^}}$", source, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"start.sh has no {name}()")
    return match.group(0)


class LogDirectoryTests(unittest.TestCase):
    def test_every_supervisor_log_directory_is_created_before_supervisord(self):
        directories = {
            str(Path(path).parent)
            for path in re.findall(r"^std(?:out|err)_logfile=(\S+)$", SUPERVISOR.read_text(), re.MULTILINE)
        }
        self.assertTrue(directories)
        main = _shell_function(START.read_text(), "main")
        before_supervisord = main.split("/usr/local/bin/supervisord", 1)[0]
        created = set()
        for line in re.findall(r"^\s*mkdir -p (.+)$", before_supervisord, re.MULTILINE):
            created.update(line.split())
        self.assertEqual(directories - created, set())


TEMPLATE = (AIO / "variables.env").read_text()

REQUIRED = {
    "DOMAIN_NAME": "hangar.example.com",
    "DATABASE_URL": "postgresql://hangar:hangar@db/hangar",
    "REDIS_URL": "redis://cache:6379",
    "AMQP_URL": "amqp://hangar:hangar@mq:5672/hangar",
    "AWS_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "access",
    "AWS_SECRET_ACCESS_KEY": "secret",
    "AWS_S3_BUCKET_NAME": "uploads",
}


def _env(path: Path) -> dict:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values.setdefault(key, value)
    return values


class SecretPersistenceTests(unittest.TestCase):
    """Each "container" is a fresh copy of the image's plane.env; the data directory persists."""

    def setUp(self):
        self.data = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.data, True)
        self.secrets = self.data / "secrets.env"
        # start.sh without its final call to main.
        self.functions = re.sub(r'^main "\$@"\s*$', "", START.read_text(), flags=re.MULTILINE)
        self.assertNotIn('main "$@"', self.functions)

    def new_container(self, plane_env: str = TEMPLATE) -> Path:
        layer = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, layer, True)
        (layer / "plane.env").write_text(plane_env)
        return layer

    def boot(self, layer: Path, **environment) -> subprocess.CompletedProcess:
        env = {
            "PATH": os.environ["PATH"],
            "HANGAR_SECRETS_FILE": str(self.secrets),
            **REQUIRED,
            **environment,
        }
        return subprocess.run(
            ["bash", "-e", "-c", self.functions + "\nupdate_env_file\n"],
            cwd=layer,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def boot_ok(self, layer: Path, **environment) -> dict:
        result = self.boot(layer, **environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return _env(layer / "plane.env")

    def test_first_boot_generates_secrets_on_the_data_volume(self):
        env = self.boot_ok(self.new_container())
        stored = _env(self.secrets)
        for name in ("SECRET_KEY", "LIVE_SERVER_SECRET_KEY"):
            with self.subTest(name=name):
                self.assertRegex(stored[name], r"^[A-Za-z0-9]{50}$")
                self.assertEqual(env[name], stored[name])
        self.assertNotEqual(stored["SECRET_KEY"], stored["LIVE_SERVER_SECRET_KEY"])
        self.assertEqual(stat.S_IMODE(self.secrets.stat().st_mode), 0o600)

    def test_a_restart_keeps_the_secrets(self):
        layer = self.new_container()
        first = self.boot_ok(layer)
        second = self.boot_ok(layer)
        for name in ("SECRET_KEY", "LIVE_SERVER_SECRET_KEY"):
            self.assertEqual(second[name], first[name])

    def test_a_recreated_container_keeps_the_secrets(self):
        first = self.boot_ok(self.new_container())
        recreated = self.boot_ok(self.new_container())
        for name in ("SECRET_KEY", "LIVE_SERVER_SECRET_KEY"):
            with self.subTest(name=name):
                self.assertEqual(recreated[name], first[name])

    def test_secrets_a_container_kept_in_its_layer_move_to_the_data_volume(self):
        """A container started by an older image holds its generated keys in plane.env."""
        old_layer = re.sub(r"^SECRET_KEY=.*$", "SECRET_KEY=keptFromTheOldLayer", TEMPLATE, flags=re.MULTILINE)
        old_layer = re.sub(
            r"^LIVE_SERVER_SECRET_KEY=.*$",
            "LIVE_SERVER_SECRET_KEY=liveKeptFromTheOldLayer",
            old_layer,
            flags=re.MULTILINE,
        )
        self.assertNotEqual(old_layer, TEMPLATE)
        env = self.boot_ok(self.new_container(old_layer))
        self.assertEqual(env["SECRET_KEY"], "keptFromTheOldLayer")
        self.assertEqual(_env(self.secrets)["SECRET_KEY"], "keptFromTheOldLayer")
        self.assertEqual(_env(self.secrets)["LIVE_SERVER_SECRET_KEY"], "liveKeptFromTheOldLayer")

        recreated = self.boot_ok(self.new_container())
        self.assertEqual(recreated["SECRET_KEY"], "keptFromTheOldLayer")
        self.assertEqual(recreated["LIVE_SERVER_SECRET_KEY"], "liveKeptFromTheOldLayer")

    def test_an_explicit_secret_wins_and_is_not_written_to_the_volume(self):
        env = self.boot_ok(self.new_container(), SECRET_KEY="operator&chosen|value\\x")
        self.assertEqual(env["SECRET_KEY"], "operator&chosen|value\\x")
        self.assertNotIn("SECRET_KEY", _env(self.secrets))

    def test_a_template_value_in_the_environment_counts_as_unset(self):
        for name, template in (
            ("SECRET_KEY", "60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5"),
            ("LIVE_SERVER_SECRET_KEY", "secret-key"),
        ):
            with self.subTest(name=name):
                env = self.boot_ok(self.new_container(), **{name: template})
                self.assertNotEqual(env[name], template)
                self.assertEqual(env[name], _env(self.secrets)[name])

    def test_start_fails_when_the_secrets_cannot_be_kept(self):
        blocker = self.data / "not-a-directory"
        blocker.write_text("")
        self.secrets = blocker / "secrets.env"
        result = self.boot(self.new_container())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not write", result.stderr)


class EnvFileQuotingTests(unittest.TestCase):
    """Values reach plane.env and the services verbatim (sed and xargs altered them)."""

    def run_functions(self, plane_env: str, body: str) -> subprocess.CompletedProcess:
        functions = re.sub(r'^main "\$@"\s*$', "", START.read_text(), flags=re.MULTILINE)
        layer = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, layer, True)
        (layer / "plane.env").write_text(plane_env)
        result = subprocess.run(
            ["bash", "-e", "-c", functions + "\n" + body],
            cwd=layer,
            env={"PATH": os.environ["PATH"]},
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result.layer = layer
        return result

    def test_update_env_value_writes_special_characters_verbatim(self):
        value = r"a&b|c\d e/f"
        result = self.run_functions(
            "AWS_SECRET_ACCESS_KEY=old\nOTHER=1\n",
            f"update_env_value AWS_SECRET_ACCESS_KEY '{value}'\n",
        )
        self.assertEqual(
            (result.layer / "plane.env").read_text(), f"AWS_SECRET_ACCESS_KEY={value}\nOTHER=1\n"
        )

    def test_update_env_value_keeps_a_value_when_given_none(self):
        result = self.run_functions("KEPT=1\n", "update_env_value KEPT ''\nupdate_env_value ADDED ''\n")
        self.assertEqual((result.layer / "plane.env").read_text(), "KEPT=1\nADDED=\n")

    def test_plane_env_is_exported_without_word_splitting(self):
        result = self.run_functions(
            "# comment=ignored\n"
            'CERT_ACME_DNS="acme_dns cloudflare token"\n'
            "SPACED=two words\n"
            "URL=postgresql://u:p@h/d?a=b\n"
            "SINGLE='quoted'\n",
            "export_env_file\n"
            'printf "%s\\n" "$CERT_ACME_DNS" "$SPACED" "$URL" "$SINGLE"\n',
        )
        self.assertEqual(
            result.stdout.splitlines(),
            ["acme_dns cloudflare token", "two words", "postgresql://u:p@h/d?a=b", "quoted"],
        )


if __name__ == "__main__":
    unittest.main()
