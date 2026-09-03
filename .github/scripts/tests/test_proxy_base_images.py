# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import re
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROXY_DOCKERFILE = REPOSITORY_ROOT / "apps" / "proxy" / "Dockerfile.ce"


class ProxyBaseImageTests(unittest.TestCase):
    def test_caddy_builder_and_runtime_are_patch_and_digest_pinned(self):
        dockerfile = PROXY_DOCKERFILE.read_text(encoding="utf-8")
        references = re.findall(
            r"^FROM docker\.io/library/caddy:(\d+\.\d+\.\d+)(-builder)?-alpine@(sha256:[0-9a-f]{64})(?: AS \S+)?$",
            dockerfile,
            flags=re.MULTILINE,
        )

        self.assertEqual(len(references), 2)
        self.assertEqual({version for version, _, _ in references}, {"2.11.4"})
        self.assertEqual({variant for _, variant, _ in references}, {"-builder", ""})


if __name__ == "__main__":
    unittest.main()
