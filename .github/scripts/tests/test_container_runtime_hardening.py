# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class ContainerRuntimeHardeningTests(unittest.TestCase):
    def _read(self, relative_path):
        return (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")

    def test_production_alpine_images_refresh_security_packages(self):
        paths = (
            "apps/admin/Dockerfile.admin",
            "apps/api/Dockerfile.api",
            "apps/live/Dockerfile.live",
            "apps/proxy/Dockerfile.ce",
            "apps/space/Dockerfile.space",
            "apps/web/Dockerfile.web",
            "deployments/aio/community/Dockerfile",
        )
        for path in paths:
            with self.subTest(path=path):
                dockerfile = self._read(path)
                self.assertIn("ARG APK_SECURITY_PATCH=2026-09-08", dockerfile)
                self.assertIn("apk upgrade --no-cache --available", dockerfile)

    def test_python_runtime_images_use_patched_base(self):
        self.assertIn("FROM python:3.12.12-alpine", self._read("apps/api/Dockerfile.api"))
        self.assertIn(
            "FROM python:3.12.12-alpine AS runner",
            self._read("deployments/aio/community/Dockerfile"),
        )

    def test_node_runtimes_do_not_depend_on_global_npm(self):
        for path in ("apps/live/Dockerfile.live", "apps/space/Dockerfile.space"):
            with self.subTest(path=path):
                self.assertIn("/usr/local/lib/node_modules/npm", self._read(path))
        self.assertIn(
            'CMD ["./node_modules/.bin/react-router-serve", "./build/server/index.js"]',
            self._read("apps/space/Dockerfile.space"),
        )
        self.assertIn(
            "command=./node_modules/.bin/react-router-serve ./build/server/index.js",
            self._read("deployments/aio/community/supervisor.conf"),
        )

    def test_custom_caddy_asserts_security_module_floors(self):
        dockerfile = self._read("apps/proxy/Dockerfile.ce")
        for module in (
            "golang.org/x/crypto@v0.55.0",
            "golang.org/x/net@v0.57.0",
            "golang.org/x/text@v0.41.0",
            "google.golang.org/grpc@v1.83.1",
            "go.opentelemetry.io/otel@v1.44.0",
            "go.opentelemetry.io/otel/sdk@v1.44.0",
        ):
            with self.subTest(module=module):
                self.assertIn(module, dockerfile)
        self.assertEqual(dockerfile.count("go version -m /usr/bin/caddy"), 4)


if __name__ == "__main__":
    unittest.main()
