# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""S28: plane.env and every copy the installers keep of it are 0600.

plane.env holds SECRET_KEY and the database, broker, cache and object-storage
credentials. Up to hangar-v0.3.0 `install.sh` and `swarm.sh` copied it to
`plane.env.bak` and `archive/<timestamp>.env` with a bare `cp`, and moved the
release's `variables.env` into place as plane.env with a bare `mv`, so all of
them took the umask's mode: 0664 or 0644, readable by every local user.

These tests run the real upgrade and backup actions of `install.sh` against a
scratch install directory under `umask 002`, with Docker replaced, run the
`download` step of both installers, and scan every script under
`deployments/` for an env file copied or moved past the safe helpers.
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
COMMUNITY = REPOSITORY_ROOT / "deployments" / "cli" / "community"
INSTALL = COMMUNITY / "install.sh"
SWARM = REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh"
SCRIPTS = (INSTALL, SWARM)
HELPERS = ("copyEnvFile", "moveEnvFile", "fileMode", "restrictToOwner", "protectEnvFiles")

# Answers every call the upgrade and backup actions make: the images are
# published for this architecture, no volume exists, and `docker cp` copies a
# data directory with a file in it.
FAKE_DOCKER = """#!/usr/bin/env bash
case "$1 $2" in
    "manifest inspect") printf '"architecture": "amd64"\\n"architecture": "arm64"\\n'; exit 0 ;;
    "volume inspect") exit 1 ;;
    "volume ls") exit 0 ;;
esac
if [ "$1" == "cp" ]; then
    dest="${@: -1}"
    mkdir -p "$dest" && echo data > "$dest/PG_VERSION"
    exit 0
fi
for arg in "$@"; do
    if [ "$arg" == "ps" ]; then
        echo 0123456789ab
        exit 0
    fi
done
exit 0
"""


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _function(source: str, name: str, script: Path) -> str:
    match = re.search(rf"^function {name}\(\)\s*\{{.*?^}}$", source, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"{script.name} has no {name}()")
    return match.group(0)


def _functions(script: Path, names: tuple) -> str:
    source = script.read_text()
    return "\n".join(_function(source, name, script) for name in names) + "\n"


def _env(path: Path) -> dict:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


class Scratch:
    """A directory holding an install from an earlier release, created loose."""

    def __init__(self, cleanup):
        self.root = Path(tempfile.mkdtemp())
        cleanup(shutil.rmtree, self.root, True)
        self.install_dir = self.root / "plane-app"
        self.archive = self.install_dir / "archive"
        self.archive.mkdir(parents=True)
        self.archive.chmod(0o775)
        self.env = self.install_dir / "plane.env"
        lines = (COMMUNITY / "variables.env").read_text().splitlines()
        lines = [line for line in lines if not line.startswith(("APP_RELEASE=", "WEB_URL="))]
        lines += ["APP_RELEASE=v0.0.1", "WEB_URL=https://hangar.example.com"]
        self.env.write_text("\n".join(lines) + "\n")
        self.env.chmod(0o664)
        # What an earlier upgrade left behind.
        self.backup = self.install_dir / "plane.env.bak"
        self.backup.write_text("SECRET_KEY=from-an-earlier-upgrade\n")
        self.backup.chmod(0o664)
        self.archived = self.archive / "1700000000.env"
        self.archived.write_text("SECRET_KEY=from-an-earlier-upgrade\n")
        self.archived.chmod(0o644)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)

    def run_installer(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.root),
            "HANGAR_ASSUME_YES": "1",
            "HANGAR_INSTALL_SOURCE_DIR": str(COMMUNITY),
            "HANGAR_RELEASE": "v9.9.9",
        }
        return subprocess.run(
            ["bash", "-c", 'umask 002 && exec bash "$0" "$@"', str(INSTALL), *arguments],
            cwd=self.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )


class ComposeUpgradeTests(unittest.TestCase):
    """`setup.sh upgrade`, run end to end with Docker replaced."""

    @classmethod
    def setUpClass(cls):
        cls.scratch = Scratch(cls.addClassCleanup)
        cls.result = cls.scratch.run_installer("--yes", "upgrade")

    def test_the_upgrade_completes(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout + self.result.stderr)
        self.assertIn("PLEASE VALIDATE AND START SERVICES", self.result.stdout)

    def test_every_env_file_is_for_the_owner_only(self):
        env_files = [self.scratch.env, self.scratch.backup, *self.scratch.archive.glob("*.env")]
        # plane.env, plane.env.bak, the copy this upgrade archived, and the
        # one an earlier upgrade archived.
        self.assertEqual(len(env_files), 4, env_files)
        for path in env_files:
            with self.subTest(path=path.name):
                self.assertEqual(_mode(path), 0o600, oct(_mode(path)))

    def test_the_archive_directory_is_for_the_owner_only(self):
        self.assertEqual(_mode(self.scratch.archive), 0o700)

    def test_the_upgrade_archived_the_previous_plane_env(self):
        archived = [path for path in self.scratch.archive.glob("*.env") if path != self.scratch.archived]
        self.assertEqual(len(archived), 1)
        self.assertEqual(_env(archived[0])["APP_RELEASE"], "v0.0.1")
        self.assertEqual(_env(self.scratch.env)["APP_RELEASE"], "v9.9.9")

    def test_tightening_an_earlier_release_is_reported_once(self):
        notices = [line for line in self.result.stderr.splitlines() if line.startswith("NOTICE: restricted")]
        self.assertEqual(len(notices), 1, self.result.stderr)
        for name in ("archive", "plane.env", "plane.env.bak", "archive/1700000000.env"):
            self.assertIn(f" {name}", notices[0])
        self.assertNotIn(str(self.scratch.install_dir), notices[0])


class FreshInstallTests(unittest.TestCase):
    def test_a_new_install_writes_plane_env_for_the_owner_only(self):
        scratch = Scratch(self.addCleanup)
        shutil.rmtree(scratch.install_dir)
        result = scratch.run_installer("--yes", "install")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(_mode(scratch.env), 0o600)
        self.assertEqual(_mode(scratch.archive), 0o700)
        self.assertEqual(list(scratch.archive.iterdir()), [])
        # The install directory itself keeps the umask's mode.
        self.assertEqual(_mode(scratch.install_dir), 0o775)
        self.assertNotIn("NOTICE: restricted", result.stderr)

    def test_a_tightened_install_is_left_alone(self):
        scratch = Scratch(self.addCleanup)
        first = scratch.run_installer("--yes", "upgrade")
        self.assertEqual(first.returncode, 0, first.stderr)
        second = scratch.run_installer("--yes", "upgrade")
        self.assertIn("You are already using the latest release", second.stdout)
        self.assertNotIn("NOTICE: restricted", second.stderr)


class BackupTests(unittest.TestCase):
    def test_the_backup_archives_are_for_the_owner_only(self):
        scratch = Scratch(self.addCleanup)
        existing = scratch.install_dir / "backup" / "20250101-0000"
        existing.mkdir(parents=True)
        (scratch.install_dir / "backup").chmod(0o775)
        (scratch.install_dir / "docker-compose.yaml").write_text("services: {}\n")
        result = scratch.run_installer("--yes", "backup")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Backup completed successfully", result.stdout)
        backup = scratch.install_dir / "backup"
        self.assertEqual(_mode(backup), 0o700)
        folders = [path for path in backup.iterdir() if path != existing]
        self.assertEqual(len(folders), 1)
        self.assertEqual(_mode(folders[0]), 0o700)
        archives = sorted(path.name for path in folders[0].iterdir())
        self.assertEqual(
            archives, ["object-storage.tar.gz", "pgdata.tar.gz", "rabbitmq_data.tar.gz", "redisdata.tar.gz"]
        )
        for name in archives:
            with self.subTest(archive=name):
                self.assertEqual(_mode(folders[0] / name), 0o600)


class DownloadTests(unittest.TestCase):
    """The `download` step of both installers, with the release files staged."""

    STUBS = (
        "function checkSecretKeyRotation() { :; }\n"
        "function generateStorageCredentials() { :; }\n"
        "function generateSecrets() { :; }\n"
        "function finishDownload() { :; }\n"
        "function updateCustomVariables() { :; }\n"
        # install.sh stages the files itself; swarm.sh downloads them.
        'function stageDeploymentFiles() { cp "$RELEASE_DIR"/* "$1"/; }\n'
        'function downloadReleaseAssets() { cp "$RELEASE_DIR"/* "$1"/; }\n'
    )

    def _download(self, script: Path) -> Scratch:
        scratch = Scratch(self.addCleanup)
        release = scratch.root / "release"
        release.mkdir()
        (release / "docker-compose.yml").write_text("services: {}\n")
        (release / "variables.env").write_text("APP_RELEASE=v9.9.9\nWEB_URL=\nSECRET_KEY=\n")
        names = HELPERS + ("getEnvValue", "updateEnvFile", "syncEnvFile", "download")
        program = (
            "umask 002\nOS_NAME=Linux\n"
            + _functions(script, names)
            + self.STUBS
            + 'protectEnvFiles\ndownload "false"\n'
        )
        environment = {
            "PATH": "/usr/bin:/bin",
            "SCRIPT_DIR": str(scratch.root),
            "PLANE_INSTALL_DIR": str(scratch.install_dir),
            "DOCKER_ENV_PATH": str(scratch.env),
            "MIGRATE_STORAGE_SCRIPT": str(scratch.install_dir / "migrate-object-storage.sh"),
            "RELEASE_DIR": str(release),
            # swarm.sh writes the release it downloaded into plane.env.
            "APP_RELEASE": "v9.9.9",
        }
        result = subprocess.run(
            ["bash", "-c", program], env=environment, capture_output=True, text=True, timeout=60, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return scratch

    def test_both_installers_keep_every_copy_for_the_owner_only(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                scratch = self._download(script)
                self.assertEqual(_mode(scratch.archive), 0o700)
                self.assertEqual(_mode(scratch.env), 0o600)
                copies = list(scratch.archive.glob("*.env"))
                self.assertEqual(len(copies), 2)
                for path in copies:
                    self.assertEqual(_mode(path), 0o600, path.name)
                # swarm.sh removes plane.env.bak once synced; install.sh keeps it.
                if script == INSTALL:
                    self.assertEqual(_mode(scratch.backup), 0o600)
                else:
                    self.assertFalse(scratch.backup.exists())
                # The values of the previous plane.env were carried over.
                self.assertEqual(_env(scratch.env)["WEB_URL"], "https://hangar.example.com")


class HelperTests(unittest.TestCase):
    def _run(self, script: Path, body: str, scratch: Path) -> subprocess.CompletedProcess:
        program = "umask 002\n" + _functions(script, HELPERS) + body
        return subprocess.run(
            ["bash", "-c", program],
            env={"PATH": "/usr/bin:/bin", "PLANE_INSTALL_DIR": str(scratch)},
            cwd=scratch,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_a_copy_is_0600_even_from_a_loose_source_onto_a_loose_file(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name), tempfile.TemporaryDirectory() as directory:
                scratch = Path(directory)
                (scratch / "plane.env").write_text("SECRET_KEY=x\n")
                (scratch / "plane.env").chmod(0o664)
                (scratch / "existing.env").write_text("old\n")
                (scratch / "existing.env").chmod(0o666)
                result = self._run(
                    script,
                    "copyEnvFile plane.env new.env && copyEnvFile plane.env existing.env\n",
                    scratch,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                for name in ("new.env", "existing.env"):
                    self.assertEqual(_mode(scratch / name), 0o600, name)
                    self.assertEqual((scratch / name).read_text(), "SECRET_KEY=x\n")

    def test_a_move_lands_0600(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name), tempfile.TemporaryDirectory() as directory:
                scratch = Path(directory)
                (scratch / "variables.env").write_text("APP_RELEASE=v1\n")
                (scratch / "variables.env").chmod(0o644)
                result = self._run(script, "moveEnvFile variables.env plane.env\n", scratch)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((scratch / "variables.env").exists())
                self.assertEqual(_mode(scratch / "plane.env"), 0o600)

    def test_only_group_and_other_access_is_removed(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name), tempfile.TemporaryDirectory() as directory:
                scratch = Path(directory)
                (scratch / "loose").write_text("")
                (scratch / "loose").chmod(0o754)
                (scratch / "tight").write_text("")
                (scratch / "tight").chmod(0o400)
                result = self._run(script, 'restrictToOwner "$PWD/loose" "$PWD/tight" "$PWD/missing"\n', scratch)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(_mode(scratch / "loose"), 0o700)
                self.assertEqual(_mode(scratch / "tight"), 0o400)
                self.assertEqual(
                    result.stderr.strip(),
                    "NOTICE: restricted to the owner, because other local users could read them: loose",
                )

    def test_both_installers_carry_the_same_helpers(self):
        install = INSTALL.read_text()
        swarm = SWARM.read_text()
        for name in HELPERS:
            with self.subTest(helper=name):
                self.assertEqual(_function(install, name, INSTALL), _function(swarm, name, SWARM))

    def test_both_installers_tighten_an_earlier_release_on_every_run(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                self.assertIn('\nprint_header\nprotectEnvFiles\naskForAction "$@"\n', source)
                self.assertIn('( umask 077 && mkdir -p "$PLANE_INSTALL_DIR/archive" )\n', source)


# A cp or mv command, not `docker cp`.
COPY_OR_MOVE = re.compile(r"(?:^|[\s;&|(])(?<!docker )(cp|mv)\s")
# An env file: plane.env, its copies, variables.env, secrets.env, or a
# variable naming one.
ENV_FILE = re.compile(r"\.env\b|ENV_PATH|ENV_FILE|SECRETS_FILE")
# Reviewed exceptions, by script and command.
ALLOWED = {
    # The all-in-one image build copies the template, which holds no secret,
    # into the build context; start.sh writes secrets.env and rewrites
    # plane.env with umask 077 inside the container.
    ("deployments/aio/community/build.sh", "cp ./variables.env $DIST_DIR/plane.env"),
}


class NoBareEnvCopyTests(unittest.TestCase):
    def test_no_deployment_script_copies_an_env_file_past_the_helpers(self):
        offending = []
        scripts = sorted((REPOSITORY_ROOT / "deployments").rglob("*.sh"))
        self.assertGreaterEqual(len(scripts), 7)
        for path in scripts:
            relative = str(path.relative_to(REPOSITORY_ROOT))
            for number, line in enumerate(path.read_text().splitlines(), 1):
                command = line.strip()
                if command.startswith("#"):
                    continue
                if COPY_OR_MOVE.search(command) and ENV_FILE.search(command):
                    if (relative, command) not in ALLOWED:
                        offending.append(f"{relative}:{number}: {command}")
        self.assertEqual(offending, [], "copy or move env files with copyEnvFile or moveEnvFile")

    def test_the_scan_finds_a_bare_copy(self):
        for command in (
            'cp "$DOCKER_ENV_PATH" "$PLANE_INSTALL_DIR/plane.env.bak"',
            'mv $PLANE_INSTALL_DIR/variables-upgrade.env $DOCKER_ENV_PATH',
            'cp "$DOCKER_ENV_PATH" "${DOCKER_ENV_PATH}.bak"',
        ):
            with self.subTest(command=command):
                self.assertTrue(COPY_OR_MOVE.search(command) and ENV_FILE.search(command))
        self.assertIsNone(COPY_OR_MOVE.search('docker cp -q "$ID:/data/." "$DIR/"'))

    def test_every_allowed_exception_still_exists(self):
        for relative, command in ALLOWED:
            with self.subTest(script=relative):
                lines = [line.strip() for line in (REPOSITORY_ROOT / relative).read_text().splitlines()]
                self.assertIn(command, lines)


if __name__ == "__main__":
    unittest.main()
