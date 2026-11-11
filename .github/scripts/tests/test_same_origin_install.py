"""Non-Helm installs must reach their own origin and the release they asked for.

The published web, admin and space images used to carry the chart's placeholder
origin (`https://hangar.example.com`) compiled in, and only the Helm chart
replaced it at runtime through `config.js`. Compose, Swarm and AIO installs
therefore sent every API call to a host they do not control, and the browser
blocked them. The images now carry no origin: the frontends use the page's own
origin unless a runtime `config.js` names one.

The Compose and Swarm installers resolved "stable" through GitHub's
`/releases/latest`, which never returns a pre-release, and every Hangar release
is one. They also fetched release assets from `v…` while the tags are
`hangar-v…`, so a fresh install stopped before it began.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "build-branch.yml"
FRONTENDS = ("web", "admin", "space")
INSTALLERS = (
    REPOSITORY_ROOT / "deployments" / "cli" / "community" / "install.sh",
    REPOSITORY_ROOT / "deployments" / "swarm" / "community" / "swarm.sh",
)
ORIGIN_VARIABLES = ("API", "WEB", "ADMIN", "SPACE", "LIVE")

RELEASES_FIXTURE = """[
  {"tag_name": "hangar-v0.1.0-rc.71", "prerelease": true, "draft": false},
  {"tag_name": "hangar-v0.1.0-rc.70", "prerelease": true, "draft": false}
]"""


def _function(script: Path, name: str) -> str:
    match = re.search(rf"^function {name}\(\)\{{?.*?^}}$", script.read_text(), re.DOTALL | re.MULTILINE)
    if match is None:
        raise AssertionError(f"{script.name} has no {name}()")
    return match.group(0)


class FrontendOriginTests(unittest.TestCase):
    def test_release_images_compile_in_no_public_origin(self):
        workflow = WORKFLOW.read_text()
        for variable in ORIGIN_VARIABLES:
            self.assertNotRegex(workflow, rf"VITE_{variable}_BASE_URL=")

    def test_release_builds_refuse_a_frontend_with_the_placeholder_origin(self):
        workflow = WORKFLOW.read_text()
        self.assertIn("name: Check the frontend has no compiled-in public origin", workflow)
        self.assertIn("""contains(fromJSON('["web", "admin", "space"]'), matrix.image)""", workflow)

    def test_the_default_runtime_config_names_no_origin(self):
        for app in FRONTENDS:
            config = (REPOSITORY_ROOT / "apps" / app / "public" / "config.js").read_text()
            self.assertIn("Object.freeze({})", config, app)
            self.assertNotIn("://", config, app)

    def test_frontends_read_origins_through_the_runtime_config(self):
        pattern = re.compile(r"process\.env\.VITE_(?:" + "|".join(ORIGIN_VARIABLES) + r")_BASE_URL")
        allowed = {
            # The shared constants: runtime config first, build-time value second.
            REPOSITORY_ROOT / "packages" / "constants" / "src" / "endpoints.ts",
            # A server-side loader; it skips the request when no origin is set.
            REPOSITORY_ROOT / "apps" / "space" / "app" / "issues" / "[anchor]" / "layout.tsx",
        }
        offenders = []
        for root in [REPOSITORY_ROOT / "apps" / app for app in FRONTENDS] + [REPOSITORY_ROOT / "packages"]:
            for path in root.rglob("*.ts*"):
                if "node_modules" in path.parts or path in allowed:
                    continue
                for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                    if pattern.search(line) and not line.lstrip().startswith("//"):
                        offenders.append(f"{path.relative_to(REPOSITORY_ROOT)}:{number}")
        self.assertEqual(offenders, [])

    def test_the_spaces_metadata_loader_skips_the_request_without_an_origin(self):
        source = (REPOSITORY_ROOT / "apps" / "space" / "app" / "issues" / "[anchor]" / "layout.tsx").read_text()
        guard = source.index("if (!apiBaseUrl)")
        self.assertLess(guard, source.index("await fetch("))


class InstallerReleaseTests(unittest.TestCase):
    def _latest(self, script: Path, response: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as scratch:
            fake_curl = Path(scratch) / "curl"
            fixture = Path(scratch) / "releases.json"
            fixture.write_text(response)
            fake_curl.write_text(f'#!/bin/sh\necho "$@" > "{scratch}/args"\ncat "{fixture}"\n')
            fake_curl.chmod(0o755)
            result = subprocess.run(
                ["bash", "-c", _function(script, "checkLatestRelease") + "\ncheckLatestRelease"],
                capture_output=True,
                text=True,
                env={"GH_REPO": "szymczag/hangar", "PATH": f"{scratch}:/usr/bin:/bin"},
            )
            result.curl_args = (Path(scratch) / "args").read_text() if (Path(scratch) / "args").exists() else ""
            return result

    def test_the_newest_pre_release_is_the_latest_release(self):
        for script in INSTALLERS:
            result = self._latest(script, RELEASES_FIXTURE)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "v0.1.0-rc.71", script.name)
            self.assertIn("/repos/szymczag/hangar/releases?", result.curl_args)
            self.assertNotIn("/releases/latest", result.curl_args)

    def test_a_release_list_without_hangar_tags_stops_the_install(self):
        for script in INSTALLERS:
            result = self._latest(script, '[{"tag_name": "v1.4.0"}]')
            self.assertNotEqual(result.returncode, 0, script.name)
            self.assertEqual(result.stdout.strip(), "", script.name)

    def test_release_assets_are_fetched_from_the_hangar_tag(self):
        for script in INSTALLERS:
            source = script.read_text()
            self.assertNotIn("$RELEASE_DOWNLOAD_URL/$APP_RELEASE/", source, script.name)
            self.assertIn("$RELEASE_DOWNLOAD_URL/hangar-$APP_RELEASE/docker-compose.yml", source, script.name)
            self.assertNotIn("$GH_REPO/releases/latest", source, script.name)

    def test_a_saved_release_tag_is_read_as_an_image_tag(self):
        for script in INSTALLERS:
            self.assertIn("APP_RELEASE=${APP_RELEASE#hangar-}", script.read_text(), script.name)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    unittest.main()
