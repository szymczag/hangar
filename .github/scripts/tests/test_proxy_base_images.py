# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROXY_DOCKERFILE = REPOSITORY_ROOT / "apps" / "proxy" / "Dockerfile.ce"


class ProxyBaseImageTests(unittest.TestCase):
    def setUp(self):
        self.dockerfile = PROXY_DOCKERFILE.read_text(encoding="utf-8")

    def test_every_base_image_is_patch_and_digest_pinned(self):
        bases = re.findall(r"^FROM (\S+)", self.dockerfile, flags=re.MULTILINE)
        self.assertEqual(len(bases), 2)
        for base in bases:
            with self.subTest(base=base):
                self.assertRegex(base, r"^docker\.io/library/[a-z]+:\d+\.\d+\.\d+-alpine@sha256:[0-9a-f]{64}$")

    def test_caddy_is_built_by_a_patched_go_toolchain(self):
        # The official caddy builder images lag behind Go security releases
        # (2.11.7 and 2.11.8 ship Go 1.27.3; CVE-2026-97054 is fixed in 1.27.4),
        # so the build stage uses the golang image and installs xcaddy itself.
        builder = re.findall(
            r"^FROM docker\.io/library/golang:(\d+)\.(\d+)\.(\d+)-alpine@sha256:[0-9a-f]{64} AS caddy-builder$",
            self.dockerfile,
            flags=re.MULTILINE,
        )
        self.assertEqual(len(builder), 1)
        self.assertGreaterEqual(tuple(int(part) for part in builder[0]), (1, 27, 4))
        self.assertIn("CADDY_VERSION=v2.11.7", self.dockerfile)

    def test_runtime_is_the_matching_caddy_release(self):
        runtime = re.findall(
            r"^FROM docker\.io/library/caddy:(\d+\.\d+\.\d+)-alpine@sha256:[0-9a-f]{64}$",
            self.dockerfile,
            flags=re.MULTILINE,
        )
        self.assertEqual(runtime, ["2.11.7"])


if __name__ == "__main__":
    unittest.main()
