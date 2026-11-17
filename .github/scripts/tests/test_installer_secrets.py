# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The installers must not leave a deployment on published secrets.

The templates used to ship `plane` as the database and broker password and
`change-this-key-on-deployment` as SECRET_KEY and LIVE_SERVER_SECRET_KEY.
`install.sh` (Compose) and `swarm.sh` (Swarm) now generate them, with one
asymmetry that matters to every existing deployment:

* SECRET_KEY and LIVE_SERVER_SECRET_KEY are replaced on install and upgrade.
  A new key costs one sign-in.
* POSTGRES_PASSWORD and RABBITMQ_PASSWORD are generated only for a new
  deployment. Postgres and RabbitMQ keep the password they were created with
  in their volumes, so rotating plane.env alone would lock the API out.

These tests run the real functions from each script against a scratch
`plane.env`, with the volume listing replaced.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INSTALL = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "install.sh"
SWARM = REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh"
SCRIPTS = (INSTALL, SWARM)
COMMUNITY = REPOSITORY_ROOT / "deployments" / "cli" / "community"
VARIABLES_PATH = COMMUNITY / "variables.env"
COMPOSE_PATH = COMMUNITY / "docker-compose.yml"
SETTINGS_PATH = REPOSITORY_ROOT / "apps" / "api" / "plane" / "settings" / "common.py"
ENTRYPOINT_PATH = REPOSITORY_ROOT / "apps" / "api" / "bin" / "docker-entrypoint-common.sh"
LIVE_ENV_PATH = REPOSITORY_ROOT / "apps" / "live" / "src" / "env.ts"

FUNCTIONS = (
    "getEnvValue",
    "updateEnvFile",
    "randomSecret",
    "isListed",
    "dataVolumeExists",
    "keepLegacyConnection",
    "envSetting",
    "generateServicePassword",
    "generateSecrets",
    "isNewDeployment",
    "checkSecretKeyRotation",
)

# What a deployment from an earlier release has in plane.env.
LEGACY_ENV = [
    "PGHOST=plane-db",
    "POSTGRES_USER=plane",
    "POSTGRES_PASSWORD=plane",
    "POSTGRES_DB=plane",
    "POSTGRES_PORT=5432",
    "DATABASE_URL=",
    "RABBITMQ_HOST=plane-mq",
    "RABBITMQ_PORT=5672",
    "RABBITMQ_USER=plane",
    "RABBITMQ_PASSWORD=plane",
    "RABBITMQ_VHOST=plane",
    "AMQP_URL=",
    "SECRET_KEY=change-this-key-on-deployment",
    "LIVE_SERVER_SECRET_KEY=change-this-key-on-deployment",
]
LEGACY_COMPOSE = (
    "  DATABASE_URL: ${DATABASE_URL:-postgresql://plane:plane@plane-db/plane}\n"
    "  AMQP_URL: ${AMQP_URL:-amqp://plane:plane@plane-mq:5672/plane}\n"
)


def _function(source: str, name: str, script: Path) -> str:
    match = re.search(rf"^function {name}\(\)\s*\{{.*?^}}$", source, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"{script.name} has no {name}()")
    return match.group(0)


def _program(script: Path, body: str) -> str:
    source = script.read_text()
    parts = [_function(source, name, script) for name in FUNCTIONS]
    # The one call that reaches Docker, replaced: FAKE_VOLUMES lists the
    # volumes, and FAKE_DOCKER_DOWN makes the call fail.
    stub = (
        "function listVolumes() {\n"
        '    [ -n "$FAKE_DOCKER_DOWN" ] && return 1\n'
        '    printf "%s\\n" $FAKE_VOLUMES\n'
        "}\n"
    )
    return "OS_NAME=Linux\n" + "\n".join(parts) + "\n" + stub + body


def _env(path: Path) -> dict:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _template() -> list:
    return [line for line in VARIABLES_PATH.read_text().splitlines() if "=" in line and not line.startswith("#")]


class Run:
    def __init__(self, env: dict, stderr: str):
        self.env = env
        self.stderr = stderr


def _generate(
    script: Path,
    lines: list,
    volumes: tuple = (),
    previous_env: bool = False,
    previous_compose: str = "",
    docker_down: bool = False,
    runs: int = 1,
) -> Run:
    with tempfile.TemporaryDirectory() as scratch:
        env_path = Path(scratch) / "plane.env"
        env_path.write_text("\n".join(lines) + "\n")
        previous_compose_path = ""
        if previous_compose:
            previous_compose_path = str(Path(scratch) / "previous.docker-compose.yml")
            Path(previous_compose_path).write_text(previous_compose)
        environment = {
            "DOCKER_ENV_PATH": str(env_path),
            "DEPLOYMENT_NAME": "plane-app",
            "FAKE_VOLUMES": " ".join(volumes),
            "PREVIOUS_ENV_EXISTS": "1" if previous_env else "0",
            "PREVIOUS_COMPOSE_PATH": previous_compose_path,
            "PATH": "/usr/bin:/bin",
        }
        if docker_down:
            environment["FAKE_DOCKER_DOWN"] = "1"
        result = subprocess.run(
            ["bash", "-c", _program(script, "generateSecrets\n" * runs)],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
        return Run(_env(env_path), result.stderr)


class FreshInstallTests(unittest.TestCase):
    def test_a_fresh_install_generates_every_secret(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                first = _generate(script, _template()).env
                second = _generate(script, _template()).env
                self.assertRegex(first["SECRET_KEY"], r"^[A-Za-z0-9]{50}$")
                self.assertRegex(first["LIVE_SERVER_SECRET_KEY"], r"^[A-Za-z0-9]{50}$")
                self.assertRegex(first["POSTGRES_PASSWORD"], r"^[A-Za-z0-9]{32}$")
                self.assertRegex(first["RABBITMQ_PASSWORD"], r"^[A-Za-z0-9]{32}$")
                for name in ("SECRET_KEY", "LIVE_SERVER_SECRET_KEY", "POSTGRES_PASSWORD", "RABBITMQ_PASSWORD"):
                    self.assertNotEqual(first[name], second[name], name)
                # The API connects with the generated passwords, not a URL.
                self.assertEqual(first["DATABASE_URL"], "")
                self.assertEqual(first["AMQP_URL"], "")

    def test_an_install_before_the_first_start_still_counts_as_new(self):
        # plane.env from an older template, but no volume yet.
        run = _generate(INSTALL, LEGACY_ENV)
        self.assertRegex(run.env["POSTGRES_PASSWORD"], r"^[A-Za-z0-9]{32}$")
        self.assertRegex(run.env["RABBITMQ_PASSWORD"], r"^[A-Za-z0-9]{32}$")

    def test_a_second_run_keeps_what_the_first_generated(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                with tempfile.TemporaryDirectory() as scratch:
                    env_path = Path(scratch) / "plane.env"
                    env_path.write_text("\n".join(_template()) + "\n")
                    environment = {
                        "DOCKER_ENV_PATH": str(env_path),
                        "DEPLOYMENT_NAME": "plane-app",
                        "FAKE_VOLUMES": "",
                        "PATH": "/usr/bin:/bin",
                    }
                    program = ["bash", "-c", _program(script, "generateSecrets\n")]
                    subprocess.run(program, check=True, capture_output=True, env=environment)
                    first = env_path.read_text()
                    # The second run sees the volumes the first start created.
                    environment["FAKE_VOLUMES"] = "plane-app_pgdata plane-app_rabbitmq_data"
                    environment["PREVIOUS_ENV_EXISTS"] = "1"
                    result = subprocess.run(program, check=True, capture_output=True, text=True, env=environment)
                    self.assertEqual(first, env_path.read_text())
                    self.assertEqual(result.stderr, "")

    def test_an_explicit_url_keeps_its_password(self):
        lines = [line for line in _template() if not line.startswith(("DATABASE_URL=", "AMQP_URL="))]
        lines += ["DATABASE_URL=postgresql://me:pw@db.example.com/hangar", "AMQP_URL=amqp://me:pw@mq.example.com/hangar"]
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                env = _generate(script, lines).env
                self.assertEqual(env["POSTGRES_PASSWORD"], "")
                self.assertEqual(env["RABBITMQ_PASSWORD"], "")
                self.assertEqual(env["DATABASE_URL"], "postgresql://me:pw@db.example.com/hangar")


class UpgradeTests(unittest.TestCase):
    VOLUMES = ("plane-app_pgdata", "plane-app_rabbitmq_data", "other_pgdata")

    def test_an_upgrade_replaces_the_template_keys_and_keeps_the_passwords(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                run = _generate(script, LEGACY_ENV, volumes=self.VOLUMES, previous_env=True)
                self.assertRegex(run.env["SECRET_KEY"], r"^[A-Za-z0-9]{50}$")
                self.assertRegex(run.env["LIVE_SERVER_SECRET_KEY"], r"^[A-Za-z0-9]{50}$")
                self.assertEqual(run.env["POSTGRES_PASSWORD"], "plane")
                self.assertEqual(run.env["RABBITMQ_PASSWORD"], "plane")
                self.assertEqual(run.env["DATABASE_URL"], "")
                self.assertEqual(run.env["AMQP_URL"], "")
                self.assertIn("NOTICE: SECRET_KEY", run.stderr)
                self.assertIn("NOTICE: LIVE_SERVER_SECRET_KEY", run.stderr)
                self.assertIn("signed out once", run.stderr)
                self.assertIn("WARNING: POSTGRES_PASSWORD", run.stderr)
                self.assertIn("WARNING: RABBITMQ_PASSWORD", run.stderr)
                self.assertIn("README", run.stderr)

    def test_every_template_key_is_replaced(self):
        for script in SCRIPTS:
            for secret_key, live_key in (
                ("60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5", "htbqvBJAgpm9bzvf3r4urJer0ENReatceh"),
                ('"change-this-key-on-deployment"', "secret-key"),
                ("", '"secret-key"'),
            ):
                with self.subTest(script=script.name, secret_key=secret_key, live_key=live_key):
                    lines = [line for line in LEGACY_ENV if not line.startswith(("SECRET_KEY=", "LIVE_SERVER_SECRET_KEY="))]
                    lines += [f"SECRET_KEY={secret_key}", f"LIVE_SERVER_SECRET_KEY={live_key}"]
                    env = _generate(script, lines, volumes=self.VOLUMES, previous_env=True).env
                    self.assertRegex(env["SECRET_KEY"], r"^[A-Za-z0-9]{50}$")
                    self.assertRegex(env["LIVE_SERVER_SECRET_KEY"], r"^[A-Za-z0-9]{50}$")

    def test_an_upgrade_never_rotates_a_password_it_cannot_prove_is_unused(self):
        # Compose: Docker unreachable. Swarm: the volumes live on another node.
        cases = (
            (INSTALL, dict(docker_down=True)),
            (SWARM, dict(docker_down=True, previous_env=True)),
            (SWARM, dict(volumes=(), previous_env=True)),
        )
        for script, options in cases:
            with self.subTest(script=script.name, options=options):
                run = _generate(script, LEGACY_ENV, **options)
                self.assertEqual(run.env["POSTGRES_PASSWORD"], "plane")
                self.assertEqual(run.env["RABBITMQ_PASSWORD"], "plane")
                self.assertIn("WARNING: POSTGRES_PASSWORD", run.stderr)

    def test_the_volumes_of_another_project_do_not_count(self):
        run = _generate(INSTALL, LEGACY_ENV, volumes=("other_pgdata", "plane-app_pgdata_old", "xplane-app_rabbitmq_data"))
        self.assertNotEqual(run.env["POSTGRES_PASSWORD"], "plane")
        self.assertNotEqual(run.env["RABBITMQ_PASSWORD"], "plane")

    def test_the_compose_project_name_decides_which_volumes_are_ours(self):
        lines = LEGACY_ENV + ["COMPOSE_PROJECT_NAME=hangar"]
        run = _generate(INSTALL, lines, volumes=("hangar_pgdata", "hangar_rabbitmq_data"))
        self.assertEqual(run.env["POSTGRES_PASSWORD"], "plane")
        self.assertEqual(run.env["RABBITMQ_PASSWORD"], "plane")

    def test_an_upgrade_keeps_operator_values(self):
        lines = [
            "POSTGRES_PASSWORD=OperatorDbPassword1",
            "RABBITMQ_PASSWORD=OperatorMqPassword1",
            "SECRET_KEY=operator-secret-key-with=equals&amp/slash\\backslash",
            "LIVE_SERVER_SECRET_KEY=operator-live-key",
            "DATABASE_URL=",
            "AMQP_URL=",
        ]
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                run = _generate(script, lines, volumes=self.VOLUMES, previous_env=True)
                self.assertEqual(run.env, dict(line.split("=", 1) for line in lines))
                self.assertEqual(run.stderr, "")


class LegacyConnectionTests(unittest.TestCase):
    """The old compose file connected with plane:plane whatever plane.env said."""

    VOLUMES = ("plane-app_pgdata", "plane-app_rabbitmq_data")

    def _changed(self, name, value):
        return [line for line in LEGACY_ENV if not line.startswith(f"{name}=")] + [f"{name}={value}"]

    def test_settings_changed_after_creation_keep_the_old_connection(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                lines = self._changed("POSTGRES_PASSWORD", "changed-later")
                lines = [line for line in lines if not line.startswith("RABBITMQ_USER=")] + ["RABBITMQ_USER=someone"]
                run = _generate(
                    script, lines, volumes=self.VOLUMES, previous_env=True, previous_compose=LEGACY_COMPOSE
                )
                self.assertEqual(run.env["DATABASE_URL"], "postgresql://plane:plane@plane-db/plane")
                self.assertEqual(run.env["AMQP_URL"], "amqp://plane:plane@plane-mq:5672/plane")
                self.assertEqual(run.env["POSTGRES_PASSWORD"], "changed-later")
                self.assertIn("WARNING: DATABASE_URL", run.stderr)
                self.assertIn("WARNING: AMQP_URL", run.stderr)

    def test_unchanged_settings_need_no_url(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                run = _generate(
                    script, LEGACY_ENV, volumes=self.VOLUMES, previous_env=True, previous_compose=LEGACY_COMPOSE
                )
                self.assertEqual(run.env["DATABASE_URL"], "")
                self.assertEqual(run.env["AMQP_URL"], "")

    def test_a_current_compose_file_or_an_explicit_url_is_left_alone(self):
        lines = self._changed("POSTGRES_PASSWORD", "generated-by-this-release")
        current = COMPOSE_PATH.read_text()
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                run = _generate(script, lines, volumes=self.VOLUMES, previous_env=True, previous_compose=current)
                self.assertEqual(run.env["DATABASE_URL"], "")
                explicit = self._changed("DATABASE_URL", "postgresql://me:pw@db.example.com/hangar")
                explicit = [line for line in explicit if not line.startswith("POSTGRES_PASSWORD=")]
                explicit.append("POSTGRES_PASSWORD=other")
                run = _generate(script, explicit, volumes=self.VOLUMES, previous_compose=LEGACY_COMPOSE)
                self.assertEqual(run.env["DATABASE_URL"], "postgresql://me:pw@db.example.com/hangar")


class CalendarCapacityGuardTests(unittest.TestCase):
    """SECRET_KEY keys identifiers Google Calendar capacity stores.

    Replacing a template key on a deployment that uses the feature is refused
    unless HANGAR_ROTATE_SECRET_KEY=1, before anything is downloaded.
    """

    def _check(self, script: Path, lines, rotate: str = "") -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as scratch:
            env_path = Path(scratch) / "plane.env"
            if lines is not None:
                env_path.write_text("\n".join(lines) + "\n")
            before = env_path.read_text() if lines is not None else None
            environment = {"DOCKER_ENV_PATH": str(env_path), "PATH": "/usr/bin:/bin"}
            if rotate:
                environment["HANGAR_ROTATE_SECRET_KEY"] = rotate
            result = subprocess.run(
                ["bash", "-c", _program(script, "checkSecretKeyRotation\n")],
                capture_output=True,
                text=True,
                env=environment,
            )
            if lines is not None:
                self.assertEqual(env_path.read_text(), before)
            return result

    def test_a_template_key_with_calendar_capacity_is_refused(self):
        for script in SCRIPTS:
            for key in ("change-this-key-on-deployment", '"change-this-key-on-deployment"', ""):
                with self.subTest(script=script.name, key=key):
                    result = self._check(script, [f"SECRET_KEY={key}", "ENABLE_GOOGLE_CALENDAR_CAPACITY=1"])
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("ENABLE_GOOGLE_CALENDAR_CAPACITY=1", result.stderr)
                    self.assertIn("HANGAR_ROTATE_SECRET_KEY=1", result.stderr)
                    self.assertIn("Nothing has been changed", result.stderr)

    def test_the_override_and_everything_else_pass(self):
        cases = (
            (["SECRET_KEY=change-this-key-on-deployment", "ENABLE_GOOGLE_CALENDAR_CAPACITY=1"], "1"),
            (["SECRET_KEY=change-this-key-on-deployment", "ENABLE_GOOGLE_CALENDAR_CAPACITY=0"], ""),
            (["SECRET_KEY=change-this-key-on-deployment"], ""),
            (["SECRET_KEY=operator-key", "ENABLE_GOOGLE_CALENDAR_CAPACITY=1"], ""),
            (None, ""),
        )
        for script in SCRIPTS:
            for lines, rotate in cases:
                with self.subTest(script=script.name, lines=lines, rotate=rotate):
                    result = self._check(script, lines, rotate)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
        # Only exactly 1 overrides.
        result = self._check(INSTALL, ["SECRET_KEY=", "ENABLE_GOOGLE_CALENDAR_CAPACITY=1"], "yes")
        self.assertEqual(result.returncode, 1)

    def test_the_guard_runs_before_anything_changes(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                download = _function(source, "download", script)
                first = [line.strip() for line in download.splitlines()[1:] if line.strip()]
                self.assertIn("checkSecretKeyRotation || exit 1", first[:3])
                upgrade = _function(source, "upgrade", script)
                self.assertLess(
                    upgrade.index("checkSecretKeyRotation || exit 1"),
                    upgrade.index("checkLatestRelease"),
                )


class EnvFileTests(unittest.TestCase):
    def _round_trip(self, script: Path, value: str) -> str:
        with tempfile.TemporaryDirectory() as scratch:
            env_path = Path(scratch) / "plane.env"
            env_path.write_text("DATABASE_URL=\nOTHER=1\n")
            body = 'updateEnvFile DATABASE_URL "$VALUE" "$DOCKER_ENV_PATH"\ngetEnvValue DATABASE_URL "$DOCKER_ENV_PATH"\n'
            result = subprocess.run(
                ["bash", "-c", _program(script, body)],
                check=True,
                capture_output=True,
                text=True,
                env={"DOCKER_ENV_PATH": str(env_path), "VALUE": value, "PATH": "/usr/bin:/bin"},
            )
            self.assertIn("OTHER=1", env_path.read_text())
            return result.stdout.rstrip("\n")

    def test_values_with_equals_ampersands_slashes_and_backslashes_survive(self):
        value = "postgresql://user:p%40ss@db.example.com:5432/hangar?sslmode=require&options=-c%20a=b\\x"
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertEqual(self._round_trip(script, value), value)

    def test_get_env_value_keeps_everything_after_the_first_equals(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                with tempfile.TemporaryDirectory() as scratch:
                    env_path = Path(scratch) / "plane.env"
                    env_path.write_text("SECRET_KEY=abc=def==\n")
                    result = subprocess.run(
                        ["bash", "-c", _program(script, 'getEnvValue SECRET_KEY "$DOCKER_ENV_PATH"\n')],
                        check=True,
                        capture_output=True,
                        text=True,
                        env={"DOCKER_ENV_PATH": str(env_path), "PATH": "/usr/bin:/bin"},
                    )
                    self.assertEqual(result.stdout.strip(), "abc=def==")


class WiringTests(unittest.TestCase):
    def test_both_installers_generate_after_syncing_the_env_file(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                self.assertRegex(
                    script.read_text(),
                    r"\n    syncEnvFile\n    generateStorageCredentials\n    generateSecrets\n",
                )

    def test_the_template_ships_no_secret(self):
        env = dict(line.split("=", 1) for line in _template())
        for name in ("SECRET_KEY", "LIVE_SERVER_SECRET_KEY", "POSTGRES_PASSWORD", "RABBITMQ_PASSWORD"):
            self.assertEqual(env[name], "", name)

    def test_the_insecure_lists_agree(self):
        settings = SETTINGS_PATH.read_text()
        block = re.search(r"_INSECURE_SECRET_KEYS = \{(.*?)\}", settings, re.DOTALL)
        self.assertIsNotNone(block)
        django = set(re.findall(r'"([^"]+)"', block.group(1)))

        entrypoint = ENTRYPOINT_PATH.read_text()
        block = re.search(r"INSECURE_SECRET_KEYS=\((.*?)\)", entrypoint, re.DOTALL)
        self.assertIsNotNone(block)
        self.assertEqual(set(re.findall(r'"([^"]+)"', block.group(1))), django)

        live = LIVE_ENV_PATH.read_text()
        block = re.search(r"INSECURE_LIVE_SERVER_SECRET_KEYS = \[(.*?)\]", live, re.DOTALL)
        self.assertIsNotNone(block)
        live_keys = set(re.findall(r'"([^"]+)"', block.group(1)))

        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                secret_lists = re.findall(r'local insecure_secret_keys="([^"]*)"', source)
                live_secret = re.search(r'local insecure_live_secret_keys="([^"]*)"', source).group(1).split()
                # generateSecrets and checkSecretKeyRotation each carry the list.
                self.assertEqual(len(secret_lists), 2)
                for secret in secret_lists:
                    self.assertEqual(set(secret.split()), django)
                self.assertEqual(set(live_secret), live_keys)

    def test_an_unattended_upgrade_does_not_ask(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                upgrade = _function(source, "upgrade", script)
                stubs = (
                    'function checkLatestRelease() { echo v9.9.9; }\n'
                    'function checkSecretKeyRotation() { :; }\n'
                    'function stopServices() { :; }\n'
                    'function install() { echo INSTALLED; }\n'
                    'function download() { echo INSTALLED; }\n'
                    'function objectStorageMigrationPending() { return 1; }\n'
                    'function redeployStack() { :; }\n'
                    'function docker() { return 1; }\n'
                )
                program = upgrade + "\n" + stubs + 'stack_name=plane\nAPP_RELEASE=v0.0.1\nupgrade\n'
                for assume_yes, expected in (("1", True), ("0", False)):
                    result = subprocess.run(
                        ["bash", "-c", program],
                        capture_output=True,
                        text=True,
                        stdin=subprocess.DEVNULL,
                        env={
                            "HANGAR_ASSUME_YES": assume_yes,
                            "DOCKER_ENV_PATH": "/nonexistent/plane.env",
                            "PATH": "/usr/bin:/bin",
                        },
                    )
                    self.assertEqual("INSTALLED" in result.stdout, expected, result.stdout + result.stderr)

    def test_a_named_release_skips_the_github_api(self):
        upgrade = _function(INSTALL.read_text(), "upgrade", INSTALL)
        stubs = (
            "function checkLatestRelease() { echo ASKED-GITHUB; exit 1; }\n"
            "function checkSecretKeyRotation() { :; }\n"
            "function stopServices() { :; }\n"
            'function install() { echo "INSTALLING $APP_RELEASE"; }\n'
            "function objectStorageMigrationPending() { return 1; }\n"
        )
        result = subprocess.run(
            ["bash", "-c", upgrade + "\n" + stubs + "APP_RELEASE=v0.0.1\nupgrade\n"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            env={"HANGAR_ASSUME_YES": "1", "HANGAR_RELEASE": "hangar-v9.9.9", "PATH": "/usr/bin:/bin"},
        )
        self.assertNotIn("ASKED-GITHUB", result.stdout)
        self.assertIn("INSTALLING v9.9.9", result.stdout)
        install = _function(INSTALL.read_text(), "install", INSTALL)
        self.assertIn('APP_RELEASE=${HANGAR_RELEASE#hangar-}', install)

    def test_the_yes_flag_is_accepted_anywhere(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                self.assertIn("--yes|-y) HANGAR_ASSUME_YES=1 ;;", source)
                self.assertRegex(source, r'set -- "\$\{ACTION_ARGS\[@\]\}"\n\nprint_header\naskForAction "\$@"\n')


if __name__ == "__main__":
    unittest.main()
