# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The installers verify what they download before it replaces anything.

`install.sh` (Compose) and `swarm.sh` (Swarm) fetch a release's
docker-compose.yml and variables.env, and check them against the release's
SHA256SUMS, whose Cosign signature they check first when cosign is installed.
They download into a scratch directory and move the files into place only
after that, and they fall back to a branch only when the operator set BRANCH.

These tests run the real `download` of each script against a release served
over HTTP from a scratch directory, with the steps after the download
replaced, and a `cosign` on PATH that records its arguments. The local-build
tests run the function that writes the Compose override for locally built
images against a compose file pinned the way the release workflow pins it.
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / ".github" / "scripts"
COMMUNITY = REPOSITORY_ROOT / "deployments" / "cli" / "community"
INSTALL = COMMUNITY / "install.sh"
SWARM = REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh"
SCRIPTS = (INSTALL, SWARM)
COMPOSE_PATH = COMMUNITY / "docker-compose.yml"
BUILD_PATH = COMMUNITY / "build.yml"

sys.path.insert(0, str(SCRIPTS_DIRECTORY))
_SPEC = importlib.util.spec_from_file_location("release_evidence", SCRIPTS_DIRECTORY / "release_evidence.py")
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("Cannot load release_evidence.py")
release_evidence = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault(_SPEC.name, release_evidence)
_SPEC.loader.exec_module(release_evidence)

VERSION = "v9.9.9"
GIT_TAG = f"hangar-{VERSION}"
IDENTITY = f"https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/{GIT_TAG}"
ISSUER = "https://token.actions.githubusercontent.com"

# Shared by both installers and required to stay identical.
VERIFY_FUNCTIONS = (
    "fetchAsset",
    "sha256Of",
    "releasePublishesChecksums",
    "verifyChecksumSignature",
    "verifyReleaseAssets",
    "fetchAssets",
    "downloadReleaseAssets",
)
INSTALL_ONLY = ("copyLocalAssets", "stageDeploymentFiles")
STUBS = (
    "function checkSecretKeyRotation() { :; }\n"
    "function syncEnvFile() { :; }\n"
    "function generateStorageCredentials() { :; }\n"
    "function generateSecrets() { :; }\n"
    "function updateEnvFile() { :; }\n"
    "function finishDownload() { :; }\n"
)
TOOLS = (
    "awk",
    "cat",
    "chmod",
    "cp",
    "curl",
    "date",
    "grep",
    "head",
    "ls",
    "mkdir",
    "mktemp",
    "mv",
    "rm",
    "sed",
    "tr",
    "sha256sum",
    "shasum",
    "perl",
)
FAKE_COSIGN = """#!/bin/bash
printf '%s\\n' "$@" > "$COSIGN_LOG"
exit "${COSIGN_EXIT:-0}"
"""


def _function(source: str, name: str, script: Path) -> str:
    match = re.search(rf"^function {name}\(\)\s*\{{.*?^}}$", source, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"{script.name} has no {name}()")
    return match.group(0)


def _program(script: Path, names: tuple, body: str) -> str:
    source = script.read_text()
    return "\n".join(_function(source, name, script) for name in names) + "\n" + STUBS + body


def _pinned_compose() -> str:
    digests = {name: "sha256:" + hashlib.sha256(name.encode()).hexdigest() for name in release_evidence.IMAGE_NAMES}
    return release_evidence.pin_compose(COMPOSE_PATH.read_text(), digests, version=VERSION, git_tag=GIT_TAG)


class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        self.server.requested.append(self.path.split("?", 1)[0])


class _Server:
    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        handler = functools.partial(_Handler, directory=str(self.root))
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.requested = []
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.root, ignore_errors=True)


SERVER: _Server | None = None


def setUpModule():
    global SERVER
    SERVER = _Server()


def tearDownModule():
    if SERVER is not None:
        SERVER.close()


class Result:
    def __init__(self, completed: subprocess.CompletedProcess, before: dict, after: dict, cosign_args):
        self.returncode = completed.returncode
        self.stdout = completed.stdout
        self.stderr = completed.stderr
        self.output = completed.stdout + completed.stderr
        self.before = before
        self.after = after
        self.cosign_args = cosign_args


def _snapshot(directory: Path) -> dict:
    return {
        str(path.relative_to(directory)): path.read_bytes() if path.is_file() else None
        for path in sorted(directory.rglob("*"))
    }


class ReleaseCase:
    """One release on the scratch server, its branch, and an install directory."""

    def __init__(self, test: unittest.TestCase):
        self.test = test
        self.base = Path(tempfile.mkdtemp(dir=SERVER.root, prefix=test.id().rsplit(".", 1)[-1] + "-"))
        self.name = self.base.name
        self.release = self.base / "releases" / "download" / GIT_TAG
        self.branch = self.base / "raw" / "feature"
        self.release.mkdir(parents=True)
        self.branch.mkdir(parents=True)
        self.files = {
            "docker-compose.yml": _pinned_compose().encode(),
            "variables.env": (COMMUNITY / "variables.env").read_bytes(),
            "migrate-object-storage.sh": (COMMUNITY / "migrate-object-storage.sh").read_bytes(),
            "setup.sh": INSTALL.read_bytes(),
            "swarm.sh": SWARM.read_bytes(),
        }
        for name, content in self.files.items():
            (self.release / name).write_bytes(content)
            (self.branch / name).write_bytes(b"# branch\n" + content)
        self.write_checksums()
        (self.release / "SHA256SUMS.sigstore.json").write_text('{"mediaType": "test"}\n')
        self.scratch = Path(tempfile.mkdtemp())
        test.addCleanup(shutil.rmtree, self.scratch, True)
        self.bin = self.scratch / "bin"
        self.bin.mkdir()

    def write_checksums(self):
        entries = release_evidence.collect_checksums(self.release)
        (self.release / "SHA256SUMS").write_text(release_evidence.format_checksums(entries))

    def tools(self, cosign: bool, omit: tuple = ()):
        for tool in TOOLS:
            if tool in omit:
                continue
            found = shutil.which(tool)
            if found:
                (self.bin / tool).symlink_to(found)
        if cosign:
            fake = self.bin / "cosign"
            fake.write_text(FAKE_COSIGN)
            fake.chmod(0o755)

    def run(
        self,
        script: Path,
        *,
        cosign: bool = True,
        cosign_exit: int = 0,
        require: str = "",
        branch: str = "",
        source_dir: str = "",
        omit_tools: tuple = (),
        release: str = VERSION,
    ) -> Result:
        self.tools(cosign, omit_tools)
        install_dir = self.scratch / "plane-app"
        (install_dir / "archive").mkdir(parents=True)
        compose_name = "docker-compose.yaml" if script == INSTALL else "docker-compose.yml"
        (install_dir / compose_name).write_text("# the previous compose file\n")
        (install_dir / "plane.env").write_text("PREVIOUS=1\n")
        (install_dir / "migrate-object-storage.sh").write_text("# the previous helper\n")
        before = _snapshot(install_dir)
        names = VERIFY_FUNCTIONS + (INSTALL_ONLY if script == INSTALL else ()) + ("download",)
        cosign_log = self.scratch / "cosign.args"
        environment = {
            "PATH": str(self.bin),
            "SCRIPT_DIR": str(self.scratch),
            "PLANE_INSTALL_DIR": str(install_dir),
            "DOCKER_ENV_PATH": str(install_dir / "plane.env"),
            "MIGRATE_STORAGE_SCRIPT": str(install_dir / "migrate-object-storage.sh"),
            "APP_RELEASE": release,
            "RELEASE_DOWNLOAD_URL": f"{SERVER.url}/{self.name}/releases/download",
            "FALLBACK_DOWNLOAD_URL": f"{SERVER.url}/{self.name}/raw/feature",
            "BRANCH": branch or "preview",
            "BRANCH_REQUESTED": branch,
            "HANGAR_REQUIRE_SIGNATURE": require,
            "HANGAR_INSTALL_SOURCE_DIR": source_dir,
            "COSIGN_LOG": str(cosign_log),
            "COSIGN_EXIT": str(cosign_exit),
        }
        completed = subprocess.run(
            [shutil.which("bash"), "-c", _program(script, names, 'download "false"\necho FINISHED\n')],
            capture_output=True,
            check=False,
            text=True,
            env=environment,
            timeout=60,
        )
        cosign_args = cosign_log.read_text().splitlines() if cosign_log.exists() else None
        return Result(completed, before, _snapshot(install_dir), cosign_args)

    def requested(self, kind: str) -> list:
        prefix = f"/{self.name}/{kind}/"
        return [path for path in SERVER.httpd.requested if path.startswith(prefix)]

    def expected_cosign_args(self, install_dir: str) -> list:
        return [
            "verify-blob",
            "--bundle",
            f"{install_dir}/SHA256SUMS.sigstore.json",
            "--certificate-identity",
            IDENTITY,
            "--certificate-oidc-issuer",
            ISSUER,
            f"{install_dir}/SHA256SUMS",
        ]


class DownloadTestCase(unittest.TestCase):
    def assertInstalled(self, case: ReleaseCase, script: Path, result: Result):
        self.assertEqual(result.returncode, 0, result.output)
        self.assertIn("FINISHED", result.stdout)
        compose_name = "docker-compose.yaml" if script == INSTALL else "docker-compose.yml"
        self.assertEqual(result.after[compose_name], case.files["docker-compose.yml"])
        self.assertEqual(result.after["plane.env"], case.files["variables.env"])
        self.assertFalse([name for name in result.after if name.startswith(".download.")], result.after.keys())

    def assertUnchanged(self, result: Result):
        self.assertNotEqual(result.returncode, 0, result.output)
        self.assertNotIn("FINISHED", result.stdout)
        self.assertEqual(result.after, result.before)
        self.assertIn("Nothing in", result.stdout)


class VerificationTests(DownloadTestCase):
    def test_a_signed_release_whose_files_match_is_installed(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                result = case.run(script)
                self.assertInstalled(case, script, result)
                if script == INSTALL:
                    self.assertEqual(result.after["migrate-object-storage.sh"], case.files["migrate-object-storage.sh"])
                self.assertIn(f"Downloading the deployment files of release {GIT_TAG}", result.stdout)
                self.assertIn("SHA256SUMS is signed by the Hangar release workflow", result.stdout)
                self.assertIn("Verified docker-compose.yml variables.env", result.stdout)
                # The signature is checked against the tag's workflow identity,
                # spelled out in the script, and the issuer, nothing else.
                self.assertEqual(len(result.cosign_args), 8, result.cosign_args)
                staging = Path(result.cosign_args[2]).parent
                self.assertEqual(result.cosign_args, case.expected_cosign_args(str(staging)))
                self.assertEqual(staging.parent.name, "plane-app")
                self.assertTrue(staging.name.startswith(".download."))
                self.assertEqual(case.requested("raw"), [])

    def test_the_identity_is_the_one_the_release_workflow_signs_with(self):
        self.assertEqual(release_evidence.certificate_identity(GIT_TAG), IDENTITY)
        self.assertEqual(release_evidence.OIDC_ISSUER, ISSUER)
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                function = _function(script.read_text(), "verifyChecksumSignature", script)
                self.assertIn(
                    'local identity="https://github.com/szymczag/hangar/.github/workflows/build-branch.yml'
                    '@refs/tags/hangar-$APP_RELEASE"',
                    function,
                )
                self.assertIn('local issuer="https://token.actions.githubusercontent.com"', function)

    def test_a_file_that_does_not_match_changes_nothing(self):
        for script in SCRIPTS:
            for name in ("docker-compose.yml", "variables.env"):
                with self.subTest(script=script.name, file=name):
                    case = ReleaseCase(self)
                    with (case.release / name).open("ab") as tampered:
                        tampered.write(b"# tampered\n")
                    result = case.run(script)
                    self.assertUnchanged(result)
                    self.assertIn(f"ERROR: {name} does not match SHA256SUMS of release {GIT_TAG}", result.stderr)

    def test_a_tampered_optional_helper_is_refused_too(self):
        case = ReleaseCase(self)
        with (case.release / "migrate-object-storage.sh").open("ab") as tampered:
            tampered.write(b"rm -rf /\n")
        result = case.run(INSTALL)
        self.assertUnchanged(result)
        self.assertIn("ERROR: migrate-object-storage.sh does not match", result.stderr)

    def test_a_file_missing_from_the_checksum_list_is_refused(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                sums = (case.release / "SHA256SUMS").read_text().splitlines()
                (case.release / "SHA256SUMS").write_text(
                    "\n".join(line for line in sums if not line.endswith("  variables.env")) + "\n"
                )
                result = case.run(script)
                self.assertUnchanged(result)
                self.assertIn("ERROR: variables.env is not listed in SHA256SUMS", result.stderr)

    def test_a_signature_that_does_not_verify_changes_nothing(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                result = case.run(script, cosign_exit=1)
                self.assertUnchanged(result)
                self.assertIn(f"ERROR: SHA256SUMS of release {GIT_TAG} is not signed by {IDENTITY}", result.stderr)

    def test_a_missing_signature_bundle_is_refused_when_cosign_can_check_it(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                (case.release / "SHA256SUMS.sigstore.json").unlink()
                result = case.run(script)
                self.assertUnchanged(result)
                self.assertIn("SHA256SUMS.sigstore.json could not be downloaded (HTTP 404)", result.stderr)
                self.assertIsNone(result.cosign_args)

    def test_without_cosign_the_checksums_are_still_checked_with_a_warning(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                result = case.run(script, cosign=False)
                self.assertInstalled(case, script, result)
                self.assertIn("WARNING: cosign is not installed", result.stderr)
                self.assertIn("https://github.com/szymczag/hangar#verifying-release-assets", result.stderr)
                self.assertIn("HANGAR_REQUIRE_SIGNATURE=1", result.stderr)
                self.assertIn("Verified docker-compose.yml variables.env", result.stdout)

                tampered = ReleaseCase(self)
                with (tampered.release / "docker-compose.yml").open("ab") as handle:
                    handle.write(b"# tampered\n")
                self.assertUnchanged(tampered.run(script, cosign=False))

    def test_require_signature_refuses_an_install_without_cosign(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                result = case.run(script, cosign=False, require="1")
                self.assertUnchanged(result)
                self.assertIn("ERROR: cosign is not installed, and HANGAR_REQUIRE_SIGNATURE=1", result.stderr)

    def test_shasum_is_used_where_sha256sum_is_missing(self):
        if shutil.which("shasum") is None or shutil.which("perl") is None:
            self.skipTest("shasum is not installed")
        case = ReleaseCase(self)
        result = case.run(INSTALL, omit_tools=("sha256sum",))
        self.assertInstalled(case, INSTALL, result)
        tampered = ReleaseCase(self)
        with (tampered.release / "variables.env").open("ab") as handle:
            handle.write(b"X=1\n")
        self.assertUnchanged(tampered.run(INSTALL, omit_tools=("sha256sum",)))

    def test_a_release_before_the_checksums_installs_with_a_warning(self):
        for script in SCRIPTS:
            for release in ("v0.1.0", "v0.1.0-rc.72", "v0.0.9"):
                with self.subTest(script=script.name, release=release):
                    case = ReleaseCase(self)
                    old = case.release.parent / f"hangar-{release}"
                    case.release.rename(old)
                    (old / "SHA256SUMS").unlink()
                    (old / "SHA256SUMS.sigstore.json").unlink()
                    result = case.run(script, release=release)
                    self.assertEqual(result.returncode, 0, result.output)
                    self.assertIn(f"WARNING: release hangar-{release} publishes no SHA256SUMS", result.stderr)
                    self.assertIsNone(result.cosign_args)

                    strict = ReleaseCase(self)
                    old = strict.release.parent / f"hangar-{release}"
                    strict.release.rename(old)
                    (old / "SHA256SUMS").unlink()
                    result = strict.run(script, release=release, require="1")
                    self.assertUnchanged(result)
                    self.assertIn("HANGAR_REQUIRE_SIGNATURE=1 refuses files it cannot verify", result.stderr)

    def test_a_newer_release_without_checksums_is_refused(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                (case.release / "SHA256SUMS").unlink()
                result = case.run(script)
                self.assertUnchanged(result)
                self.assertIn(f"ERROR: release {GIT_TAG} has no SHA256SUMS", result.stderr)

    def test_only_releases_after_v0_1_0_must_publish_checksums(self):
        function = _function(INSTALL.read_text(), "releasePublishesChecksums", INSTALL)
        cases = {
            "v0.1.0": False,
            "v0.1.0-rc.72": False,
            "v0.0.9": False,
            "local": False,
            "stable": False,
            "v0.1.1": True,
            "v0.1.1-rc.1": True,
            "v0.2.0": True,
            "v0.10.0": True,
            "v1.0.0": True,
            "v0.08.0": True,
        }
        for release, expected in cases.items():
            with self.subTest(release=release):
                result = subprocess.run(
                    ["bash", "-c", function + "\nreleasePublishesChecksums\n"],
                    env={"APP_RELEASE": release, "PATH": "/usr/bin:/bin"},
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(result.returncode == 0, expected, result.stderr)
                self.assertEqual(result.stderr, "")


class SourceTests(DownloadTestCase):
    def test_a_release_that_cannot_be_downloaded_is_an_error_without_branch(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                (case.release / "variables.env").unlink()
                result = case.run(script)
                self.assertUnchanged(result)
                self.assertIn(f"ERROR: release {GIT_TAG} could not be downloaded", result.stderr)
                self.assertIn("BRANCH=<branch>", result.stderr)
                self.assertEqual(case.requested("raw"), [])

    def test_branch_set_by_the_operator_falls_back_unverified(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                shutil.rmtree(case.release)
                result = case.run(script, branch="feature")
                self.assertEqual(result.returncode, 0, result.output)
                self.assertIn("Using the files of branch feature", result.stderr)
                self.assertIn("they are not verified", result.stderr)
                compose_name = "docker-compose.yaml" if script == INSTALL else "docker-compose.yml"
                self.assertTrue(result.after[compose_name].startswith(b"# branch\n"))
                self.assertIsNone(result.cosign_args)

    def test_branch_set_does_not_replace_a_release_that_exists(self):
        case = ReleaseCase(self)
        result = case.run(INSTALL, branch="feature")
        self.assertEqual(result.after["docker-compose.yaml"], case.files["docker-compose.yml"])
        self.assertEqual(case.requested("raw"), [])
        self.assertIsNotNone(result.cosign_args)

    def test_require_signature_refuses_the_branch_fallback(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                case = ReleaseCase(self)
                shutil.rmtree(case.release)
                result = case.run(script, branch="feature", require="1")
                self.assertUnchanged(result)
                self.assertIn(
                    "HANGAR_REQUIRE_SIGNATURE=1 refuses the unverified files of branch feature", result.stderr
                )
                self.assertEqual(case.requested("raw"), [])

    def test_a_missing_optional_helper_is_reported(self):
        case = ReleaseCase(self)
        (case.release / "migrate-object-storage.sh").unlink()
        case.write_checksums()
        result = case.run(INSTALL)
        self.assertEqual(result.returncode, 0, result.output)
        self.assertIn("WARNING: migrate-object-storage.sh could not be downloaded", result.stderr)
        # The previous helper stays.
        self.assertEqual(result.after["migrate-object-storage.sh"], b"# the previous helper\n")
        self.assertEqual(case.requested("raw"), [])

    def test_a_source_directory_is_used_as_it_is_and_named(self):
        case = ReleaseCase(self)
        result = case.run(INSTALL, source_dir=str(COMMUNITY))
        self.assertEqual(result.returncode, 0, result.output)
        self.assertIn(f"Using the deployment files in {COMMUNITY}", result.stdout)
        self.assertEqual(result.after["docker-compose.yaml"], COMPOSE_PATH.read_bytes())
        self.assertEqual(case.requested("releases"), [])

        strict = ReleaseCase(self)
        result = strict.run(INSTALL, source_dir=str(COMMUNITY), require="1")
        self.assertUnchanged(result)
        self.assertIn(
            "HANGAR_REQUIRE_SIGNATURE=1 refuses the unverified files of HANGAR_INSTALL_SOURCE_DIR", result.stderr
        )

    def test_the_fallback_needs_branch_from_the_operator(self):
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                source = script.read_text()
                self.assertRegex(source, r"\nBRANCH_REQUESTED=\$\{BRANCH:-\}\nBRANCH=\$\{BRANCH:-preview\}\n")
                self.assertIn("HANGAR_REQUIRE_SIGNATURE=${HANGAR_REQUIRE_SIGNATURE:-0}", source)

    def test_both_installers_share_the_verification_code(self):
        install = INSTALL.read_text()
        swarm = SWARM.read_text()
        for name in VERIFY_FUNCTIONS:
            with self.subTest(function=name):
                self.assertEqual(_function(install, name, INSTALL), _function(swarm, name, SWARM))


class LocalBuildTests(unittest.TestCase):
    FUNCTIONS = ("composeFiles", "writeLocalBuildOverride")

    def _override(self, compose: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as scratch:
            compose_path = Path(scratch) / "docker-compose.yaml"
            override_path = Path(scratch) / "docker-compose.override.yaml"
            compose_path.write_text(compose)
            body = (
                "writeLocalBuildOverride myplane local || exit 1\n"
                'echo "FILES $(composeFiles)"\n'
                'cat "$DOCKER_OVERRIDE_PATH"\n'
            )
            result = subprocess.run(
                ["bash", "-c", _program(INSTALL, self.FUNCTIONS, body)],
                capture_output=True,
                check=False,
                text=True,
                env={
                    "DOCKER_FILE_PATH": str(compose_path),
                    "DOCKER_OVERRIDE_PATH": str(override_path),
                    "PATH": "/usr/bin:/bin",
                },
            )
            result.compose_path = str(compose_path)
            result.override_path = str(override_path)
            return result

    @staticmethod
    def _hangar_services(compose: str) -> dict:
        services = {}
        current = None
        in_services = False
        for line in compose.splitlines():
            if line == "services:":
                in_services = True
                continue
            if line and not line[0].isspace() and not line.startswith("#"):
                in_services = False
            match = re.match(r"^  ([A-Za-z0-9._-]+):\s*$", line)
            if in_services and match:
                current = match.group(1)
                continue
            match = re.match(r"^    image:.*/hangar-([a-z0-9-]+)", line)
            if in_services and current and match:
                services[current] = match.group(1)
        return services

    def test_the_override_points_every_hangar_service_at_the_local_images(self):
        pinned = _pinned_compose()
        self.assertNotIn("${DOCKERHUB_USER", pinned)
        expected = self._hangar_services(pinned)
        self.assertGreaterEqual(set(expected), {"web", "space", "admin", "live", "api", "worker", "migrator", "proxy"})
        for compose in (pinned, COMPOSE_PATH.read_text()):
            with self.subTest(pinned=compose is pinned):
                result = self._override(compose)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"FILES -f {result.compose_path} -f {result.override_path}", result.stdout)
                override = result.stdout.split("\n", 1)[1]
                images = dict(
                    re.findall(
                        r"^  ([A-Za-z0-9._-]+):\n    image: (\S+)\n    pull_policy: never$", override, re.MULTILINE
                    )
                )
                self.assertEqual(
                    images, {service: f"myplane/hangar-{component}:local" for service, component in expected.items()}
                )
                # The data services keep the images the release pinned.
                for service in ("plane-db", "plane-redis", "plane-mq", "plane-minio"):
                    self.assertNotIn(f"  {service}:", override)

    def test_the_override_is_valid_compose(self):
        compose = shutil.which("docker")
        if (
            compose is None
            or subprocess.run([compose, "compose", "version"], capture_output=True, check=False).returncode != 0
        ):
            self.skipTest("docker compose is not installed")
        with tempfile.TemporaryDirectory() as scratch:
            compose_path = Path(scratch) / "docker-compose.yaml"
            override_path = Path(scratch) / "docker-compose.override.yaml"
            compose_path.write_text(_pinned_compose())
            subprocess.run(
                ["bash", "-c", _program(INSTALL, self.FUNCTIONS, "writeLocalBuildOverride myplane local\n")],
                check=True,
                capture_output=True,
                env={
                    "DOCKER_FILE_PATH": str(compose_path),
                    "DOCKER_OVERRIDE_PATH": str(override_path),
                    "PATH": "/usr/bin:/bin",
                },
            )
            env_file = Path(scratch) / "plane.env"
            env_file.write_text((COMMUNITY / "variables.env").read_text())
            result = subprocess.run(
                [
                    compose,
                    "compose",
                    "-f",
                    str(compose_path),
                    "-f",
                    str(override_path),
                    "--env-file",
                    str(env_file),
                    "config",
                    "--images",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            hangar = sorted({line for line in result.stdout.split() if "/hangar-" in line})
            self.assertTrue(hangar)
            self.assertTrue(
                all(line.startswith("myplane/hangar-") and line.endswith(":local") for line in hangar), hangar
            )

    def test_a_compose_file_without_hangar_images_is_refused(self):
        result = self._override("services:\n  db:\n    image: postgres\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("No Hangar image found", result.stderr)

    def test_without_an_override_only_the_release_file_is_used(self):
        result = subprocess.run(
            ["bash", "-c", _program(INSTALL, ("composeFiles",), "composeFiles\n")],
            capture_output=True,
            check=False,
            text=True,
            env={
                "DOCKER_FILE_PATH": "/x/docker-compose.yaml",
                "DOCKER_OVERRIDE_PATH": "/nonexistent/override.yaml",
                "PATH": "/usr/bin:/bin",
            },
        )
        self.assertEqual(result.stdout.strip(), "-f /x/docker-compose.yaml")

    def test_every_compose_command_uses_the_override(self):
        source = INSTALL.read_text()
        commands = re.findall(r"\$COMPOSE_CMD[^\"\n]*", source)
        project = [command for command in commands if "build.yml" not in command]
        self.assertGreaterEqual(len(project), 6)
        for command in project:
            with self.subTest(command=command):
                self.assertTrue(command.startswith("$COMPOSE_CMD $(composeFiles) "), command)

    def _finish(self, local_build: str, override_exists: bool) -> tuple:
        with tempfile.TemporaryDirectory() as scratch:
            compose_path = Path(scratch) / "docker-compose.yaml"
            override_path = Path(scratch) / "docker-compose.override.yaml"
            compose_path.write_text(_pinned_compose())
            if override_exists:
                override_path.write_text("services: {}\n")
            stubs = (
                'function buildYourOwnImage() { echo "BUILD $1 $DOCKERHUB_USER $APP_RELEASE"; }\n'
                "function updateCustomVariables() { :; }\n"
            )
            names = ("composeFiles", "writeLocalBuildOverride", "finishDownload")
            source = INSTALL.read_text()
            program = (
                "\n".join(_function(source, name, INSTALL) for name in names)
                + "\n"
                + stubs
                + f'finishDownload "{local_build}"\n'
            )
            result = subprocess.run(
                ["bash", "-c", program],
                capture_output=True,
                check=False,
                text=True,
                env={
                    "DOCKER_FILE_PATH": str(compose_path),
                    "DOCKER_OVERRIDE_PATH": str(override_path),
                    "DOCKER_ENV_PATH": str(Path(scratch) / "plane.env"),
                    "COMPOSE_CMD": "echo COMPOSE",
                    "APP_RELEASE": VERSION,
                    "BRANCH": "preview",
                    "BRANCH_REQUESTED": "",
                    "PATH": "/usr/bin:/bin",
                },
            )
            override = override_path.read_text() if override_path.exists() else None
            return result, override

    def test_a_local_build_writes_the_override_and_builds_the_release_tag(self):
        result, override = self._finish("true", False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"BUILD {GIT_TAG} myplane local", result.stdout)
        self.assertIn("image: myplane/hangar-api:local", override)

    def test_published_images_remove_a_previous_override(self):
        result, override = self._finish("false", True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(override)
        self.assertRegex(result.stdout, r"COMPOSE -f \S+docker-compose\.yaml --env-file=\S+ pull --policy always")

    def test_the_build_definition_builds_from_the_repository_root(self):
        # buildYourOwnImage runs build.yml in place, so its contexts are
        # relative to deployments/cli/community.
        build = BUILD_PATH.read_text()
        contexts = re.findall(r"context: (\S+)", build)
        self.assertTrue(contexts)
        for context in contexts:
            with self.subTest(context=context):
                self.assertTrue((COMMUNITY / context).resolve().is_dir(), context)
                self.assertTrue(str((COMMUNITY / context).resolve()).startswith(str(REPOSITORY_ROOT)))
        for context, dockerfile in re.findall(r"context: (\S+)\n\s+dockerfile: (\S+)", build):
            with self.subTest(dockerfile=dockerfile):
                self.assertTrue((COMMUNITY / context / dockerfile).resolve().is_file(), dockerfile)
        self.assertIn(
            "-f $PLANE_TEMP_CODE_DIR/deployments/cli/community/build.yml build",
            _function(INSTALL.read_text(), "buildYourOwnImage", INSTALL),
        )

    def test_a_local_release_name_is_resolved_again(self):
        install = _function(INSTALL.read_text(), "install", INSTALL)
        self.assertIn('[ "$APP_RELEASE" == "stable" ] || [ "$APP_RELEASE" == "local" ]', install)


if __name__ == "__main__":
    unittest.main()
