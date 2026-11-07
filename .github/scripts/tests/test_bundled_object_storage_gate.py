# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""With USE_MINIO=0 the bundled object storage must neither serve nor be routed.

The API then keeps uploads in external storage, and the installers leave the
bundled store's login alone, so a running bundled store would sit on whatever
pair the compose file falls back to, behind the application's origin. The store
idles instead, and the proxy routes the bucket path to it only while
USE_MINIO=1. These tests run the real entrypoint against a stub `weed`.
"""

import json
import re
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILES = (
    REPOSITORY_ROOT / "deployments" / "cli" / "community" / "docker-compose.yml",
    REPOSITORY_ROOT / "docker-compose.yml",
)
CADDYFILE = REPOSITORY_ROOT / "apps" / "proxy" / "Caddyfile.ce"


def _service(path: Path, name: str) -> str:
    """The text of one top-level service in a compose file."""
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|^\S|\Z)",
        path.read_text(),
        re.DOTALL | re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"{path.name} has no {name} service")
    return match.group(1)


def _entrypoint(path: Path) -> str:
    """The shell script the bundled store runs, as its `- |` block scalar."""
    block = _service(path, "plane-minio")
    match = re.search(
        r"^    entrypoint:\n      - /bin/sh\n      - -c\n      - \|\n((?:        .*\n|\n)+)",
        block,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(
            f"{path.name}: plane-minio entrypoint is not /bin/sh -c with a block script"
        )
    return "\n".join(line[8:] for line in match.group(1).splitlines())


def _healthcheck(path: Path) -> list:
    match = re.search(
        r"^      test: (\[.*\])$", _service(path, "plane-minio"), re.MULTILINE
    )
    if match is None:
        raise AssertionError(
            f"{path.name}: plane-minio has no one-line healthcheck test"
        )
    return json.loads(match.group(1))


def _shell(value: str) -> str:
    """Undo Compose's `$$` escaping and drop the bucket interpolation."""
    return re.sub(r"\$\{[A-Z_]+:-([^}]*)\}", r"\1", value.replace("$$", "$"))


class BundledObjectStorageGateTests(unittest.TestCase):
    def _run(self, compose: Path, use_minio: str) -> tuple:
        script = _shell(_entrypoint(compose))
        with tempfile.TemporaryDirectory() as scratch:
            marker = Path(scratch) / "weed-ran"
            weed = Path(scratch) / "weed"
            weed.write_text(f"#!/bin/sh\ntouch {marker}\n")
            weed.chmod(weed.stat().st_mode | stat.S_IEXEC)
            process = subprocess.Popen(
                ["sh", "-c", script],
                env={"PATH": f"{scratch}:/usr/bin:/bin", "USE_MINIO": use_minio},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            time.sleep(1)
            running = process.poll() is None
            if running:
                process.terminate()
            code = process.wait(timeout=5)
            return marker.exists(), running, code

    def test_the_store_idles_unless_use_minio_is_1(self):
        for compose in COMPOSE_FILES:
            for value in ("0", ""):
                with self.subTest(compose=compose.name, use_minio=value):
                    weed_ran, running, code = self._run(compose, value)
                    self.assertFalse(weed_ran)
                    self.assertTrue(running)
                    # It stops promptly on SIGTERM instead of waiting for SIGKILL.
                    self.assertEqual(code, 0)

    def test_the_store_starts_when_use_minio_is_1(self):
        for compose in COMPOSE_FILES:
            with self.subTest(compose=compose.name):
                weed_ran, _, _ = self._run(compose, "1")
                self.assertTrue(weed_ran)

    def test_the_store_and_the_proxy_see_use_minio_with_the_api_default(self):
        for compose in COMPOSE_FILES:
            text = compose.read_text()
            anchor = re.search(
                r"^x-proxy-env: &proxy-env\n((?:  .*\n)+)", text, re.MULTILINE
            )
            for name in ("plane-minio", "proxy"):
                with self.subTest(compose=compose.name, service=name):
                    block = _service(compose, name)
                    if name == "proxy" and "<<: *proxy-env" in block:
                        block = anchor.group(1)
                    self.assertIn("USE_MINIO: ${USE_MINIO:-1}\n", block)
        # The bundle's API and the store agree on the default, through the shared anchors.
        bundle = COMPOSE_FILES[0].read_text()
        self.assertEqual(bundle.count("USE_MINIO: ${USE_MINIO:-1}\n"), 3)

    def test_the_idle_store_reports_healthy(self):
        for compose in COMPOSE_FILES:
            test = _healthcheck(compose)
            with self.subTest(compose=compose.name):
                self.assertEqual(test[0], "CMD-SHELL")
                result = subprocess.run(
                    ["sh", "-c", _shell(test[1])],
                    env={"PATH": "/usr/bin:/bin", "USE_MINIO": "0"},
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0)
                # While the store is in use the check still probes it.
                self.assertIn(
                    "|| wget -q -O /dev/null http://127.0.0.1:9000/healthz", test[1]
                )

    def test_the_proxy_routes_the_bucket_only_to_the_bundled_store_while_it_is_used(
        self,
    ):
        caddyfile = CADDYFILE.read_text()
        routes = [
            line.strip() for line in caddyfile.splitlines() if "plane-minio" in line
        ]
        self.assertEqual(routes, ["reverse_proxy @bundled_bucket plane-minio:9000"])
        matcher = re.search(r"@bundled_bucket \{(.*?)\n\t\}", caddyfile, re.DOTALL)
        self.assertIsNotNone(matcher)
        self.assertIn("path /{$BUCKET_NAME} /{$BUCKET_NAME}/*", matcher.group(1))
        self.assertIn('expression `"{$USE_MINIO:1}" == "1"`', matcher.group(1))


if __name__ == "__main__":
    unittest.main()
