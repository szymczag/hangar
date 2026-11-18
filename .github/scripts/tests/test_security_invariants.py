# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Fork security controls that live in configuration, pinned before upstream syncs.

FORK.md, "Security invariants", lists every control and the tests that guard it.
The controls here are images, deployment manifests, the release workflow and
source-level bans; each test fails if its control is removed or weakened, and
says which S-id it guards.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_DOCKERFILE = REPOSITORY_ROOT / "apps" / "api" / "Dockerfile.api"
API_DEV_DOCKERFILE = REPOSITORY_ROOT / "apps" / "api" / "Dockerfile.dev"
API_PYPROJECT = REPOSITORY_ROOT / "apps" / "api" / "pyproject.toml"
WEB_DOCKERFILE = REPOSITORY_ROOT / "apps" / "web" / "Dockerfile.web"
ADMIN_DOCKERFILE = REPOSITORY_ROOT / "apps" / "admin" / "Dockerfile.admin"
SPACE_DOCKERFILE = REPOSITORY_ROOT / "apps" / "space" / "Dockerfile.space"
LIVE_DOCKERFILE = REPOSITORY_ROOT / "apps" / "live" / "Dockerfile.live"
PROXY_DOCKERFILE = REPOSITORY_ROOT / "apps" / "proxy" / "Dockerfile.ce"
AIO_DOCKERFILE = REPOSITORY_ROOT / "deployments" / "aio" / "community" / "Dockerfile"
COMMUNITY_COMPOSE = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "docker-compose.yml"
CHART = REPOSITORY_ROOT / "charts" / "hangar"
BUILD_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "build-branch.yml"
ENTRYPOINT_COMMON = REPOSITORY_ROOT / "apps" / "api" / "bin" / "docker-entrypoint-common.sh"
SETUP_FORM = REPOSITORY_ROOT / "apps" / "admin" / "components" / "instance" / "setup-form.tsx"

PRODUCTION_DOCKERFILES = (
    API_DOCKERFILE,
    WEB_DOCKERFILE,
    ADMIN_DOCKERFILE,
    SPACE_DOCKERFILE,
    LIVE_DOCKERFILE,
    PROXY_DOCKERFILE,
    AIO_DOCKERFILE,
)


def stages(dockerfile: Path) -> list[tuple[str, str]]:
    """Split a Dockerfile into (FROM line, body) pairs, in order."""
    parts = re.split(r"^(FROM .*)$", dockerfile.read_text(), flags=re.MULTILINE)
    return [(parts[index], parts[index + 1]) for index in range(1, len(parts), 2)]


def final_user(dockerfile: Path) -> str | None:
    users = re.findall(r"^USER\s+(\S+)\s*$", stages(dockerfile)[-1][1], re.MULTILINE)
    return users[-1] if users else None


class ApiImageTests(unittest.TestCase):
    """S1: the API image runs as uid 10001, nothing is world-writable, and it
    installs only the locked production dependencies and ships no installer."""

    def test_runs_as_the_dedicated_unprivileged_user(self):
        source = API_DOCKERFILE.read_text()
        self.assertRegex(source, r"addgroup -g 10001 hangar")
        self.assertRegex(source, r"adduser -D -u 10001 -G hangar hangar")
        self.assertEqual(final_user(API_DOCKERFILE), "10001:10001")

    def test_no_production_image_makes_files_world_writable(self):
        # 777, any octal mode with the others-write bit, a+w, o+w, or o=...w.
        world_writable = re.compile(r"(chmod\s+(-R\s+)?|--chmod=)(\d*[2367]\b|\S*\b[ao]\+\S*w|\S*\bo=[rwxX]*w)")
        for dockerfile in PRODUCTION_DOCKERFILES:
            with self.subTest(dockerfile=dockerfile.relative_to(REPOSITORY_ROOT)):
                for line in dockerfile.read_text().splitlines():
                    self.assertIsNone(world_writable.search(line), line)

    def test_the_code_tree_is_not_writable_by_group_or_others(self):
        self.assertRegex(API_DOCKERFILE.read_text(), r"chmod -R u=rwX,g=rX,o=rX /code")

    def test_installs_only_the_locked_production_dependencies(self):
        body = stages(API_DOCKERFILE)[-1][1]
        self.assertIn("uv sync --locked --inexact --no-default-groups --group production", body)
        self.assertNotRegex(body, r"\bpip3? install\b")

    def test_runtime_image_ships_neither_pip_nor_uv(self):
        body = stages(API_DOCKERFILE)[-1][1]
        # uv is bind-mounted for the install step only, never copied in.
        self.assertIn("--mount=from=uv,source=/uv,target=/bin/uv", body)
        self.assertNotRegex(body, r"COPY\s+--from=uv\b")
        for path in ("site-packages/pip ", "site-packages/pip-*.dist-info", "/usr/local/bin/pip "):
            self.assertIn(path, body)

    def test_grpc_trusts_the_system_bundle(self):
        for dockerfile in (API_DOCKERFILE, AIO_DOCKERFILE):
            with self.subTest(dockerfile=dockerfile.relative_to(REPOSITORY_ROOT)):
                self.assertIn(
                    "ENV GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/etc/ssl/certs/ca-certificates.crt",
                    stages(dockerfile)[-1][1],
                )

    def test_uv_image_matches_the_required_version(self):
        required = re.search(r'^required-version = "==([0-9.]+)"$', API_PYPROJECT.read_text(), re.MULTILINE)
        self.assertIsNotNone(required, "apps/api/pyproject.toml no longer pins uv exactly")
        for dockerfile in (API_DOCKERFILE, API_DEV_DOCKERFILE):
            with self.subTest(dockerfile=dockerfile.name):
                self.assertRegex(
                    dockerfile.read_text(),
                    rf"(?m)^FROM ghcr\.io/astral-sh/uv:{re.escape(required.group(1))}@sha256:[0-9a-f]{{64}} AS uv$",
                )


class NginxImageTests(unittest.TestCase):
    """S2: web and admin are served by nginx-unprivileged as uid 101 with the CSP hook."""

    def test_served_by_unprivileged_nginx_as_uid_101(self):
        for dockerfile in (WEB_DOCKERFILE, ADMIN_DOCKERFILE):
            with self.subTest(dockerfile=dockerfile.name):
                from_line, _ = stages(dockerfile)[-1]
                self.assertRegex(from_line, r"^FROM docker\.io/nginxinc/nginx-unprivileged:")
                self.assertEqual(final_user(dockerfile), "101:101")

    def test_installs_the_csp_hook_and_the_header_template(self):
        for dockerfile in (WEB_DOCKERFILE, ADMIN_DOCKERFILE):
            with self.subTest(dockerfile=dockerfile.name):
                body = stages(dockerfile)[-1][1]
                self.assertIn(
                    "/app/packages/csp/nginx/15-hangar-csp.envsh /docker-entrypoint.d/15-hangar-csp.envsh", body
                )
                self.assertIn("security-headers.conf.template /etc/nginx/templates/security-headers.conf.template", body)

    def test_every_nginx_block_that_sets_headers_includes_the_security_headers(self):
        for app in ("web", "admin"):
            with self.subTest(app=app):
                config = (REPOSITORY_ROOT / "apps" / app / "nginx" / "nginx.conf").read_text()
                self.assertIn("include /tmp/nginx-conf.d/security-headers.conf;", config)
                # nginx drops inherited add_header directives in a block that sets
                # its own, so a block with add_header must include them again.
                for block in re.findall(r"location[^{]*\{[^}]*\}", config):
                    if "add_header" in block:
                        self.assertIn("security-headers.conf", block, block)

    def test_the_hook_ships_where_the_images_copy_it_from(self):
        self.assertTrue((REPOSITORY_ROOT / "packages" / "csp" / "nginx" / "15-hangar-csp.envsh").is_file())


class NodeImageTests(unittest.TestCase):
    """S3: space and live run as the image's unprivileged `node` user."""

    def test_runtime_stage_drops_to_node(self):
        for dockerfile in (SPACE_DOCKERFILE, LIVE_DOCKERFILE):
            with self.subTest(dockerfile=dockerfile.name):
                self.assertEqual(final_user(dockerfile), "node")


# S4. Base images not yet pinned by digest. This list may only shrink: a new
# unpinned base, or a pinned one losing its digest, fails the test below. The
# Hangar images the all-in-one image copies from are pinned at release time by
# release_evidence.py and are not listed.
KNOWN_UNPINNED_BASES = {
    ("apps/api/Dockerfile.api", "docker.io/library/python:3.12.12-alpine"),
    ("apps/web/Dockerfile.web", "docker.io/library/node:22-alpine"),
    ("apps/web/Dockerfile.web", "docker.io/nginxinc/nginx-unprivileged:1.31-alpine"),
    ("apps/admin/Dockerfile.admin", "docker.io/library/node:22-alpine"),
    ("apps/admin/Dockerfile.admin", "docker.io/nginxinc/nginx-unprivileged:1.31-alpine"),
    ("apps/space/Dockerfile.space", "docker.io/library/node:22-alpine"),
    ("apps/live/Dockerfile.live", "docker.io/library/node:22-alpine"),
    ("deployments/aio/community/Dockerfile", "docker.io/tonistiigi/binfmt"),
    ("deployments/aio/community/Dockerfile", "docker.io/library/node:22-alpine"),
    ("deployments/aio/community/Dockerfile", "docker.io/library/python:3.12.12-alpine"),
}


def unpinned_bases() -> set[tuple[str, str]]:
    found = set()
    for dockerfile in PRODUCTION_DOCKERFILES:
        local_stages = set()
        for from_line, _ in stages(dockerfile):
            match = re.match(r"FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", from_line, re.IGNORECASE)
            assert match, from_line
            image, alias = match.group(1), match.group(2)
            if alias:
                local_stages.add(alias)
            if image in local_stages or image.startswith("${IMAGE_PREFIX}") or "@sha256:" in image:
                continue
            found.add((str(dockerfile.relative_to(REPOSITORY_ROOT)), image))
    return found


class BaseImagePinningTests(unittest.TestCase):
    """S4: base images are pinned by digest, and the unpinned remainder only shrinks."""

    def test_no_new_unpinned_base_image(self):
        self.assertEqual(unpinned_bases() - KNOWN_UNPINNED_BASES, set())

    def test_the_known_list_is_not_stale(self):
        # Pinning one is progress: drop it from KNOWN_UNPINNED_BASES so it stays pinned.
        self.assertEqual(KNOWN_UNPINNED_BASES - unpinned_bases(), set())

    def test_the_proxy_is_pinned(self):
        for from_line, _ in stages(PROXY_DOCKERFILE):
            self.assertRegex(from_line, r"@sha256:[0-9a-f]{64}\b")


class ComposeUserTests(unittest.TestCase):
    """S5 (the part test_compose_hardening.py leaves out): no service runs as root by choice."""

    def test_no_service_overrides_its_user_to_root(self):
        users = re.findall(r"^\s+user:\s*\"?([^\"\s]+)\"?\s*$", COMMUNITY_COMPOSE.read_text(), re.MULTILINE)
        self.assertTrue(users, "the community compose file no longer sets any user")
        for user in users:
            self.assertNotRegex(user, r"^(0|root)(:|$)")

    def test_bundled_object_storage_runs_as_an_unprivileged_user(self):
        source = COMMUNITY_COMPOSE.read_text()
        block = source[source.index("\n  plane-minio:\n") :]
        block = block[: re.search(r"\n  [a-z0-9-]+:\n", block[1:]).start() + 1]
        self.assertIn('user: "1000:1000"', block)


WORKLOAD_KINDS = ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob")
EXPECTED_UIDS = {"api": "10001", "worker": "10001", "beat-worker": "10001", "migrate": "10001", "web": "101",
                 "admin": "101", "space": "1000", "live": "1000"}


def render_chart(*arguments: str) -> list[str]:
    completed = subprocess.run(
        ["helm", "template", "hangar", str(CHART), "--namespace", "hangar", "--kube-version", "1.36.2", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.split("\n---\n")


def workloads(documents: list[str]) -> dict[str, str]:
    found = {}
    for document in documents:
        kind = re.search(r"^kind: (\w+)$", document, re.MULTILINE)
        name = re.search(r"^metadata:\n  name: (\S+)$", document, re.MULTILINE)
        if kind and name and kind.group(1) in WORKLOAD_KINDS:
            found[name.group(1)] = document
    return found


@unittest.skipUnless(
    shutil.which("helm") or os.environ.get("CI"), "helm is not installed (it is on the CI runner, where this runs)"
)
class HelmSecurityContextTests(unittest.TestCase):
    """S6: every chart workload runs non-root, read-only, without privileges or capabilities."""

    @classmethod
    def setUpClass(cls):
        cls.renders = {
            "production": workloads(render_chart()),
            "evaluation": workloads(render_chart("--values", str(CHART / "ci" / "evaluation-values.yaml"))),
        }

    def test_the_render_has_the_workloads(self):
        names = set(self.renders["production"])
        for component in ("api", "web", "admin", "space", "live", "worker"):
            self.assertIn(f"hangar-hangar-{component}", names)

    def test_every_container_is_locked_down(self):
        for render, documents in self.renders.items():
            for name, document in documents.items():
                with self.subTest(render=render, workload=name):
                    containers = len(re.findall(r"^\s+image: ", document, re.MULTILINE))
                    self.assertGreater(containers, 0)
                    self.assertEqual(document.count("allowPrivilegeEscalation: false"), containers)
                    self.assertEqual(document.count("readOnlyRootFilesystem: true"), containers)
                    self.assertEqual(len(re.findall(r"capabilities:\n\s+drop:\n\s+- ALL\n", document)), containers)
                    self.assertNotRegex(document, r"capabilities:\n(\s+drop:\n\s+- ALL\n)?\s+add:")
                    # The pod and each container both refuse to start as root.
                    self.assertEqual(document.count("runAsNonRoot: true"), containers + 1)
                    self.assertNotRegex(document, r"privileged: true|runAsUser: 0\b|hostNetwork: true|hostPID: true")

    def test_application_uids(self):
        documents = self.renders["production"]
        for component, uid in EXPECTED_UIDS.items():
            with self.subTest(component=component):
                name = next(name for name in documents if re.fullmatch(rf"hangar-hangar-{component}(-\d+)?", name))
                self.assertEqual(set(re.findall(r"runAsUser: (\d+)", documents[name])), {uid})

    def test_web_runtime_config_is_mounted_over_the_image_file(self):
        document = self.renders["production"]["hangar-hangar-web"]
        self.assertRegex(
            document, r"- name: [\w-]+\n\s+mountPath: /usr/share/nginx/html/config\.js\n\s+subPath: config\.js"
        )


def workflow_jobs() -> dict[str, str]:
    source = BUILD_WORKFLOW.read_text()
    jobs_section = source[source.index("\njobs:\n") :]
    parts = re.split(r"^  ([a-z][a-z0-9_-]*):\n", jobs_section, flags=re.MULTILINE)
    return {parts[index]: parts[index + 1] for index in range(1, len(parts), 2)}


class ReleaseEvidenceTests(unittest.TestCase):
    """S16: what the release workflow proves about a tag, its images and its chart.

    test_release_workflow.py covers ordering and the checksum signature; these
    pin the individual evidence steps to the jobs that must carry them.
    """

    @classmethod
    def setUpClass(cls):
        cls.jobs = workflow_jobs()

    def test_the_release_tag_must_be_a_verified_annotated_tag_on_the_commit(self):
        setup = self.jobs["setup"]
        self.assertRegex(setup, r'object_type=\$\(jq -r \'\.object\.type\' <<< "\$tag_object"\)')
        self.assertIn('if [[ "$object_type" != "tag"', setup)
        self.assertIn("if [[ $(jq -r '.verification.verified' <<< \"$tag_data\") != \"true\" ]]; then", setup)
        self.assertIn(
            "$(jq -r '.object.sha' <<< \"$tag_data\") != \"$COMMIT_SHA\"", setup
        )

    def test_image_builds_record_full_provenance_and_an_sbom(self):
        for job in ("components", "aio"):
            with self.subTest(job=job):
                self.assertRegex(self.jobs[job], r"\n\s+provenance: mode=max\n\s+sbom: true\n")

    def test_images_and_chart_get_a_build_provenance_attestation(self):
        for job in ("components", "aio", "chart"):
            with self.subTest(job=job):
                self.assertRegex(self.jobs[job], r"uses: actions/attest-build-provenance@[0-9a-f]{40} ")

    def test_images_are_signed_and_the_signature_verified(self):
        for job in ("components", "aio"):
            with self.subTest(job=job):
                body = self.jobs[job]
                self.assertIn('cosign sign --yes "${IMAGE}@${DIGEST}"', body)
                self.assertRegex(
                    body,
                    r'cosign verify \\\n\s+--certificate-identity "\$CERTIFICATE_IDENTITY" \\\n'
                    r'\s+--certificate-oidc-issuer "https://token\.actions\.githubusercontent\.com" \\\n'
                    r'\s+"\$\{IMAGE\}@\$\{DIGEST\}"',
                )

    def test_the_chart_is_signed_and_the_signature_verified(self):
        body = self.jobs["chart"]
        self.assertIn('cosign sign --yes "$chart_ref"', body)
        self.assertRegex(
            body,
            r'cosign verify \\\n\s+--certificate-identity "\$CERTIFICATE_IDENTITY" \\\n'
            r'\s+--certificate-oidc-issuer "https://token\.actions\.githubusercontent\.com" \\\n\s+"\$chart_ref"',
        )

    def test_the_checksums_are_signed(self):
        body = self.jobs["release"]
        self.assertIn("cosign sign-blob --yes", body)
        self.assertIn("cosign verify-blob", body)
        self.assertIn("sha256sum --check --strict SHA256SUMS", body)


class EntrypointSecretKeyTests(unittest.TestCase):
    """S13: the API containers refuse to start with an empty or published SECRET_KEY."""

    def run_common(self, **environment):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        env.update(environment)
        with tempfile.TemporaryDirectory() as directory:
            return subprocess.run(
                ["bash", "-c", f'source "{ENTRYPOINT_COMMON}"; echo started'],
                cwd=directory,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_published_and_empty_keys_are_refused(self):
        for value in ("", "change-this-key-on-deployment", "60gp0byfz2dvffa45cxl20p1scy9xbpf6d8c5y0geejgkyp1b5"):
            with self.subTest(value=value):
                completed = self.run_common(SECRET_KEY=value)
                self.assertEqual(completed.returncode, 64, completed.stderr)
                self.assertNotIn("started", completed.stdout)

    def test_a_generated_key_starts(self):
        completed = self.run_common(SECRET_KEY="f" * 64)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("started", completed.stdout)


FRONTEND_ROOTS = ("apps/web", "apps/admin", "apps/space", "apps/live", "packages")
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html", ".css"}
SKIPPED_DIRECTORIES = {"node_modules", "build", "dist", ".turbo", ".react-router", "storybook-static", "coverage"}


def frontend_sources():
    for root in FRONTEND_ROOTS:
        for directory, subdirectories, files in os.walk(REPOSITORY_ROOT / root):
            subdirectories[:] = [name for name in subdirectories if name not in SKIPPED_DIRECTORIES]
            for name in files:
                path = Path(directory, name)
                if path.suffix in SOURCE_SUFFIXES:
                    yield path


def code_lines(path: Path):
    """Yield (number, line) for lines that are not comments."""
    for number, line in enumerate(path.read_text(errors="replace").splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(("//", "*", "/*", "<!--")):
            continue
        yield number, line


class FrontendSourceBanTests(unittest.TestCase):
    """S21, S25: no external image provider and no third-party analytics in the browser.

    apps/web/tests/no-third-party-scripts-contract.test.mjs bans external script
    hosts in apps/web; this sweeps every frontend app and package for the
    providers by name, which also catches a provider loaded through a package.
    """

    BANNED: ClassVar[dict[str, re.Pattern[str]]] = {
        "S21 Unsplash": re.compile(r"unsplash", re.IGNORECASE),
        "S25 analytics": re.compile(
            r"clarity\.ms|posthog-js|posthog\.(init|com)|googletagmanager|google-analytics\.com|\bgtag\(|"
            r"plausible\.io|cdn\.segment\.(com|io)|hotjar|mixpanel|fullstory|logrocket|amplitude\.com",
            re.IGNORECASE,
        ),
    }

    def test_the_sweep_sees_the_sources(self):
        files = list(frontend_sources())
        self.assertGreater(len(files), 1000)
        self.assertIn(REPOSITORY_ROOT / "apps" / "web" / "app" / "root.tsx", files)

    def test_no_banned_provider_in_frontend_code(self):
        hits = []
        for path in frontend_sources():
            if "/tests/" in path.as_posix() or path.name.endswith((".test.ts", ".test.tsx", ".test.mjs")):
                continue
            for number, line in code_lines(path):
                for name, pattern in self.BANNED.items():
                    if pattern.search(line):
                        hits.append(f"{name}: {path.relative_to(REPOSITORY_ROOT)}:{number}: {line.strip()}")
        self.assertEqual(hits, [])

    def test_no_analytics_package_is_a_frontend_dependency(self):
        banned = re.compile(r'"(posthog-js|@vercel/analytics|react-ga4?|@segment/[^"]+|mixpanel-browser|'
                            r'@amplitude/[^"]+|logrocket|@fullstory/[^"]+|@microsoft/clarity)"\s*:')
        for root in FRONTEND_ROOTS:
            for manifest in (REPOSITORY_ROOT / root).glob("**/package.json"):
                if SKIPPED_DIRECTORIES & set(manifest.relative_to(REPOSITORY_ROOT).parts):
                    continue
                with self.subTest(manifest=str(manifest.relative_to(REPOSITORY_ROOT))):
                    self.assertIsNone(banned.search(manifest.read_text()))

    def test_admin_has_no_image_provider_page(self):
        dashboard = REPOSITORY_ROOT / "apps" / "admin" / "app" / "(all)" / "(dashboard)"
        self.assertTrue(dashboard.is_dir())
        self.assertFalse((dashboard / "image").exists())


class TelemetryDefaultTests(unittest.TestCase):
    """S22: the instance setup form starts with telemetry off."""

    def test_setup_form_defaults_telemetry_off(self):
        source = SETUP_FORM.read_text()
        defaults = re.search(r"const defaultFromData: TFormData = \{(.*?)\};", source, re.DOTALL)
        self.assertIsNotNone(defaults, "the setup form's defaults moved; update this test")
        self.assertRegex(defaults.group(1), r"\bis_telemetry_enabled: false,")
        # Only an explicit "True" (the API's own redirect after a failed submit) turns it on.
        self.assertIn('telemetryParam === "True"', source)


if __name__ == "__main__":
    unittest.main()
