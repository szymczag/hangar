# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The all-in-one image sends web and God Mode the Compose images' security headers.

The web and admin images serve their builds with nginx and the headers @plane/csp
generated from each build. The all-in-one image serves the same builds with
Caddy's file_server, which sent none of them: no Content-Security-Policy, no
X-Frame-Options or frame-ancestors, no nosniff, no Referrer-Policy. It now copies
each image's header template and start-up hook and renders them into the Caddy
snippets its Caddyfile imports. These tests render a template made by the real
generator through start.sh's own function.
"""

import importlib.util
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
AIO = REPOSITORY_ROOT / "deployments" / "aio" / "community"
START = AIO / "start.sh"
RENDERER = AIO / "render-security-headers.py"
DOCKERFILE = AIO / "Dockerfile"
CADDYFILE = REPOSITORY_ROOT / "apps" / "proxy" / "Caddyfile.aio.ce"
CSP = REPOSITORY_ROOT / "packages" / "csp"
HOOK = CSP / "nginx" / "15-hangar-csp.envsh"
GENERATOR = CSP / "bin" / "nginx-headers.mjs"

_spec = importlib.util.spec_from_file_location("render_security_headers", RENDERER)
render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render)

PAGE = (
    "<!DOCTYPE html><html><head>"
    '<meta name="hangar-trusted-types" content="report"/>'
    "<script>window.__context = {};</script>"
    "</head><body></body></html>"
)


def _handle_blocks(caddyfile: str) -> dict:
    """Each handle/handle_path matcher with the body of its block."""
    blocks = {}
    for match in re.finditer(r"^\s*(handle(?:_path)?)\s+(\S+)\s*\{(.*?)^\s*\}", caddyfile, re.DOTALL | re.MULTILINE):
        blocks[match.group(2)] = match.group(3)
    return blocks


class CaddyfileTests(unittest.TestCase):
    def setUp(self):
        self.blocks = _handle_blocks(CADDYFILE.read_text())

    def test_web_and_god_mode_import_their_rendered_headers(self):
        for matcher, snippet in (("/*", "web.caddy"), ("/god-mode*", "admin.caddy")):
            with self.subTest(matcher=matcher):
                body = self.blocks[matcher]
                self.assertIn(f"import /app/proxy/security-headers/{snippet}", body)
                self.assertIn("file_server", body)

    def test_proxied_services_keep_their_own_headers(self):
        # space sends its own nonce-based policy; the API and live are not pages.
        for matcher in ("/spaces/*", "/live/*", "/api/*", "/auth/*"):
            with self.subTest(matcher=matcher):
                self.assertNotIn("security-headers", self.blocks[matcher])
                self.assertNotIn("header", self.blocks[matcher])

    def test_every_static_block_sets_headers(self):
        for matcher, body in self.blocks.items():
            if "file_server" in body:
                with self.subTest(matcher=matcher):
                    self.assertIn("import /app/proxy/security-headers/", body)


class DockerfileTests(unittest.TestCase):
    def test_copies_each_images_template_the_hook_and_the_renderer(self):
        dockerfile = DOCKERFILE.read_text()
        for line in (
            "COPY --from=web-img /etc/nginx/templates/security-headers.conf.template "
            "/app/proxy/security-headers/web.conf.template",
            "COPY --from=admin-img /etc/nginx/templates/security-headers.conf.template "
            "/app/proxy/security-headers/admin.conf.template",
            "COPY --from=web-img /docker-entrypoint.d/15-hangar-csp.envsh "
            "/app/proxy/security-headers/15-hangar-csp.envsh",
            "COPY render-security-headers.py /app/proxy/render-security-headers.py",
        ):
            with self.subTest(line=line):
                self.assertIn(line, dockerfile)

    def test_the_copied_paths_are_where_the_nginx_images_install_them(self):
        for dockerfile in ("apps/web/Dockerfile.web", "apps/admin/Dockerfile.admin"):
            with self.subTest(dockerfile=dockerfile):
                body = (REPOSITORY_ROOT / dockerfile).read_text()
                self.assertIn("/etc/nginx/templates/security-headers.conf.template", body)
                self.assertIn("/docker-entrypoint.d/15-hangar-csp.envsh", body)

    def test_start_renders_before_supervisord(self):
        main = re.search(r"^main\(\)\s*\{.*?^}$", START.read_text(), re.DOTALL | re.MULTILINE).group(0)
        self.assertLess(main.index("export_env_file"), main.index("configure_security_headers"))
        self.assertLess(main.index("configure_security_headers"), main.index("supervisord"))


@unittest.skipUnless(shutil.which("node"), "node runs the @plane/csp generator")
class RenderTests(unittest.TestCase):
    """start.sh's configure_security_headers against a template from the real generator."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.work, True)
        self.dir = self.work / "security-headers"
        self.dir.mkdir()
        shutil.copy(HOOK, self.dir / "15-hangar-csp.envsh")
        self.roots = {}
        for app in ("web", "admin"):
            root = self.work / app
            root.mkdir()
            (root / "index.html").write_text(PAGE)
            (root / "50x.html").write_text("<html>error</html>")
            build = self.work / f"{app}-build"
            build.mkdir()
            (build / "index.html").write_text(PAGE)
            subprocess.run(
                ["node", str(GENERATOR), "--html", str(build / "index.html"), "--out", str(self.dir / f"{app}.conf.template")],
                check=True,
                capture_output=True,
            )
            self.roots[app] = root
        self.functions = re.sub(r'^main "\$@"\s*$', "", START.read_text(), flags=re.MULTILINE)

    def configure(self, **environment) -> subprocess.CompletedProcess:
        env = {
            "PATH": os.environ["PATH"],
            "HANGAR_SECURITY_HEADERS_DIR": str(self.dir),
            "HANGAR_SECURITY_HEADERS_RENDERER": str(RENDERER),
            "HANGAR_WEB_ROOT": str(self.roots["web"]),
            "HANGAR_ADMIN_ROOT": str(self.roots["admin"]),
            "AWS_S3_ENDPOINT_URL": "https://s3.eu-central-1.amazonaws.com",
            "AWS_S3_BUCKET_NAME": "hangar-uploads",
            "USE_MINIO": "0",
            **environment,
        }
        return subprocess.run(
            ["bash", "-e", "-c", self.functions + '\nconfigure_security_headers\nprintf "%s\\n" "$HANGAR_CSP_IMG_SRC"\n'],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def headers(self, app: str = "web", **environment) -> dict:
        result = self.configure(**environment)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        snippet = (self.dir / f"{app}.caddy").read_text()
        self.assertRegex(snippet, r"(?m)^header \{$")
        return dict(re.findall(r'(?m)^\t(\S+) "([^"]*)"$', snippet))

    def header_lines(self, **environment) -> list:
        self.headers(**environment)
        return re.findall(r'(?m)^\t(\S+) "([^"]*)"$', (self.dir / "web.caddy").read_text())

    def test_both_apps_get_the_compose_headers(self):
        for app in ("web", "admin"):
            with self.subTest(app=app):
                headers = self.headers(app)
                self.assertEqual(headers["X-Frame-Options"], "DENY")
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["Referrer-Policy"], "strict-origin-when-cross-origin")
                self.assertEqual(headers["X-XSS-Protection"], "0")
                policy = headers["Content-Security-Policy"]
                self.assertIn("frame-ancestors 'none'", policy)
                self.assertIn("object-src 'none'", policy)
                self.assertIn("frame-src 'none'", policy)
                self.assertTrue(policy.endswith("; report-uri /api/csp-report/"), policy)
                self.assertNotIn("unsafe-inline", policy)
                self.assertNotIn("${", policy)
                self.assertEqual(
                    headers["Content-Security-Policy-Report-Only"],
                    "require-trusted-types-for 'script'; trusted-types hangar-inert default dompurify; "
                    "report-uri /api/csp-report/",
                )

    def test_the_policy_carries_the_builds_inline_script_hash(self):
        template = (self.dir / "web.conf.template").read_text()
        hashes = re.findall(r"'sha256-[^']+'", template)
        self.assertTrue(hashes)
        policy = self.headers()["Content-Security-Policy"]
        for value in hashes:
            self.assertIn(value, policy)

    def test_strict_transport_security_stays_off(self):
        self.assertIn("Strict-Transport-Security", (self.dir / "web.conf.template").read_text())
        self.assertNotIn("Strict-Transport-Security", self.headers())

    def test_object_storage_is_allowed_like_the_helm_chart(self):
        result = self.configure(HANGAR_CSP_IMG_SRC="https://cdn.example.com")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines()[-1],
            "https://s3.eu-central-1.amazonaws.com https://hangar-uploads.s3.eu-central-1.amazonaws.com "
            "https://cdn.example.com",
        )
        policy = self.headers()["Content-Security-Policy"]
        storage = "https://s3.eu-central-1.amazonaws.com https://hangar-uploads.s3.eu-central-1.amazonaws.com"
        for directive in ("img-src", "connect-src", "media-src"):
            with self.subTest(directive=directive):
                self.assertRegex(policy, rf"{directive} 'self'[^;]* {re.escape(storage)}")

    def test_report_only_and_trusted_types_modes_follow_the_hook(self):
        # Both policies are report-only: Caddy must add the field twice, as nginx
        # does, because a set field keeps only its last value.
        lines = self.header_lines(HANGAR_CSP_REPORT_ONLY="true")
        names = [name for name, _ in lines]
        self.assertNotIn("Content-Security-Policy", names)
        self.assertEqual(names.count("+Content-Security-Policy-Report-Only"), 2)
        self.assertNotIn("Content-Security-Policy-Report-Only", names)
        policies = [value for name, value in lines if name == "+Content-Security-Policy-Report-Only"]
        self.assertIn("frame-ancestors 'none'", policies[0])
        self.assertIn("require-trusted-types-for 'script'", policies[1])

        headers = self.headers(HANGAR_CSP_TRUSTED_TYPES="off")
        self.assertNotIn("Content-Security-Policy-Report-Only", headers)
        self.assertNotIn("trusted-types", headers["Content-Security-Policy"])

    def test_the_page_learns_the_trusted_types_mode_and_can_change_it_back(self):
        index = self.roots["web"] / "index.html"
        self.headers(HANGAR_CSP_TRUSTED_TYPES="enforce")
        self.assertIn('<meta name="hangar-trusted-types" content="enforce"/>', index.read_text())
        self.assertEqual((self.roots["web"] / "50x.html").read_text(), "<html>error</html>")
        self.headers()
        self.assertEqual(index.read_text(), PAGE)

    def test_start_fails_rather_than_serving_without_headers(self):
        (self.dir / "admin.conf.template").write_text("add_header X-Frame-Options \"DENY\" always;\n")
        result = self.configure()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sets no", result.stderr)

        (self.dir / "15-hangar-csp.envsh").unlink()
        self.assertNotEqual(self.configure().returncode, 0)

    def test_a_value_caddy_would_interpret_is_refused(self):
        for value in ("https://{http.request.host}", 'https://a" X-Injected "1', "https://a\\b"):
            with self.subTest(value=value):
                result = self.configure(HANGAR_CSP_CONNECT_SRC=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Caddy", result.stderr)


class TemplateParsingTests(unittest.TestCase):
    def test_an_unknown_variable_or_directive_is_refused(self):
        with self.assertRaisesRegex(render.TemplateError, "UNKNOWN"):
            render.parse_template('add_header X-Frame-Options "${UNKNOWN}" always;', {})
        with self.assertRaisesRegex(render.TemplateError, "not understood"):
            render.parse_template("proxy_pass http://elsewhere;", {})


class StorageOriginTests(unittest.TestCase):
    def test_origins_follow_the_presigning_endpoint(self):
        cases = (
            (
                {"AWS_S3_ENDPOINT_URL": "https://s3.amazonaws.com", "AWS_S3_BUCKET_NAME": "files"},
                "https://s3.amazonaws.com https://files.s3.amazonaws.com",
            ),
            (
                {
                    "AWS_S3_ENDPOINT_URL": "http://seaweedfs:8333",
                    "AWS_S3_PUBLIC_ENDPOINT_URL": "https://Files.Example.com:9443/",
                    "AWS_S3_BUCKET_NAME": "uploads",
                },
                "https://files.example.com:9443 https://uploads.files.example.com:9443",
            ),
            # Path-style only: a bucket name with a dot, an IP endpoint, USE_MINIO.
            ({"AWS_S3_ENDPOINT_URL": "https://s3.example.com", "AWS_S3_BUCKET_NAME": "my.bucket"}, "https://s3.example.com"),
            ({"AWS_S3_ENDPOINT_URL": "http://192.168.68.169:19000", "AWS_S3_BUCKET_NAME": "plane-app"}, "http://192.168.68.169:19000"),
            (
                {"AWS_S3_ENDPOINT_URL": "https://s3.example.com", "AWS_S3_BUCKET_NAME": "files", "USE_MINIO": "1"},
                "https://s3.example.com",
            ),
            ({"AWS_S3_ENDPOINT_URL": ""}, ""),
        )
        for env, origins in cases:
            with self.subTest(env=env):
                self.assertEqual(render.storage_origins(env), origins)

    def test_an_endpoint_that_is_not_a_url_is_refused(self):
        with self.assertRaises(render.TemplateError):
            render.storage_origins({"AWS_S3_ENDPOINT_URL": "s3.amazonaws.com", "AWS_S3_BUCKET_NAME": "files"})


if __name__ == "__main__":
    unittest.main()
