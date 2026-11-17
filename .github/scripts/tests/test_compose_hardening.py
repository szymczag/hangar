# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The published Compose file must keep its hardening and its pinned images.

Every service runs with no-new-privileges. The application images and the
bundled object storage run as an unprivileged user and drop every Linux
capability; the proxy keeps only the one that binds ports 80 and 443. Postgres,
Valkey and RabbitMQ start as root and switch user, so they keep the default set.

The API connects with POSTGRES_* and RABBITMQ_*, which is what the installer
generates; a URL with the old `plane:plane` login would silently bypass that.

Third-party images are pinned by digest so a re-pushed tag cannot change what
an install runs; Dependabot moves the pins (.github/dependabot.yml).

The file is parsed by indentation rather than with PyYAML, which the test
runner does not ship.
"""

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMMUNITY_COMPOSE = REPOSITORY_ROOT / "deployments" / "cli" / "community" / "docker-compose.yml"
ROOT_COMPOSE = REPOSITORY_ROOT / "docker-compose.yml"
DEPENDABOT = REPOSITORY_ROOT / ".github" / "dependabot.yml"

APPLICATION_SERVICES = {
    "web",
    "space",
    "admin",
    "live",
    "api",
    "worker",
    "import-worker",
    "mail-worker",
    "beat-worker",
    "migrator",
    "plane-minio",
}
DATA_SERVICES = {"plane-db", "plane-redis", "plane-mq"}
THIRD_PARTY_PREFIX = "docker.io/"


def services(path: Path) -> dict:
    """Map each service name to the text of its block."""
    text = path.read_text()
    section = text[text.index("\nservices:\n") + len("\nservices:\n") :]
    end = re.search(r"^\S", section, re.MULTILINE)
    if end:
        section = section[: end.start()]
    blocks, name, lines = {}, None, []
    for line in section.splitlines():
        match = re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if match:
            if name:
                blocks[name] = "\n".join(lines)
            name, lines = match.group(1), []
        elif name:
            lines.append(line)
    if name:
        blocks[name] = "\n".join(lines)
    return blocks


def key_list(block: str, key: str) -> list:
    match = re.search(rf"^    {key}:\n((?:      - .*\n?)+)", block, re.MULTILINE)
    if not match:
        return []
    return [item.strip()[2:].strip().strip('"') for item in match.group(1).splitlines()]


class CommunityComposeHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = COMMUNITY_COMPOSE.read_text()
        cls.services = services(COMMUNITY_COMPOSE)

    def test_the_parser_sees_every_service(self):
        self.assertEqual(set(self.services), APPLICATION_SERVICES | DATA_SERVICES | {"proxy"})

    def test_every_service_has_no_new_privileges(self):
        for name, block in self.services.items():
            with self.subTest(service=name):
                self.assertIn("no-new-privileges:true", key_list(block, "security_opt"))

    def test_application_services_drop_every_capability(self):
        for name in APPLICATION_SERVICES:
            with self.subTest(service=name):
                self.assertEqual(key_list(self.services[name], "cap_drop"), ["ALL"])
                self.assertEqual(key_list(self.services[name], "cap_add"), [])

    def test_the_proxy_keeps_only_the_port_binding_capability(self):
        proxy = self.services["proxy"]
        self.assertEqual(key_list(proxy, "cap_drop"), ["ALL"])
        self.assertEqual(key_list(proxy, "cap_add"), ["NET_BIND_SERVICE"])

    def test_data_services_keep_the_default_capabilities(self):
        for name in DATA_SERVICES:
            with self.subTest(service=name):
                self.assertEqual(key_list(self.services[name], "cap_drop"), [])

    def test_data_services_and_the_api_have_healthchecks(self):
        expected = {
            "plane-db": "pg_isready",
            "plane-redis": "valkey-cli",
            "plane-mq": "rabbitmq-diagnostics",
            "api": "http://localhost:8000/",
        }
        for name, probe in expected.items():
            with self.subTest(service=name):
                block = self.services[name]
                self.assertIn("    healthcheck:\n      test:", block)
                self.assertIn(probe, block)

    def test_the_api_waits_for_healthy_data_services(self):
        for name in ("api", "worker", "import-worker", "mail-worker", "beat-worker"):
            for dependency in DATA_SERVICES:
                with self.subTest(service=name, dependency=dependency):
                    self.assertRegex(
                        self.services[name],
                        rf"\n      {dependency}:\n        condition: service_healthy",
                    )

    def test_no_url_carries_the_template_login(self):
        self.assertNotIn("plane:plane", self.text)
        self.assertIn("  DATABASE_URL: ${DATABASE_URL:-}\n", self.text)
        self.assertIn("  AMQP_URL: ${AMQP_URL:-}\n", self.text)
        # Without these the API cannot build the connection the URLs used to carry.
        for name in ("POSTGRES_HOST", "RABBITMQ_USER", "RABBITMQ_PASSWORD", "RABBITMQ_HOST", "RABBITMQ_VHOST"):
            self.assertRegex(self.text, rf"\n  {name}: \$\{{")

    def test_third_party_images_are_pinned_by_digest(self):
        images = re.findall(r"^    image: (\S+)$", self.text, re.MULTILINE)
        third_party = [image for image in images if image.startswith(THIRD_PARTY_PREFIX)]
        self.assertEqual(len(third_party), 4, third_party)
        for image in third_party:
            with self.subTest(image=image):
                self.assertRegex(image, r"^docker\.io/[a-z0-9./-]+:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$")

    def test_dependabot_watches_the_pins(self):
        config = DEPENDABOT.read_text()
        entry = re.search(r"  - package-ecosystem: docker-compose\n((?:    .*\n|\s*\n)+)", config)
        self.assertIsNotNone(entry, "no docker-compose entry in dependabot.yml")
        self.assertIn("/deployments/cli/community", entry.group(1))
        self.assertIn("target-branch: preview", entry.group(1))


class RootComposeHardeningTests(unittest.TestCase):
    """The build-from-source stack runs the same images and must not lag behind."""

    def test_every_service_has_no_new_privileges(self):
        for name, block in services(ROOT_COMPOSE).items():
            with self.subTest(service=name):
                self.assertIn("no-new-privileges:true", key_list(block, "security_opt"))

    def test_application_services_drop_every_capability(self):
        blocks = services(ROOT_COMPOSE)
        for name in APPLICATION_SERVICES & set(blocks):
            with self.subTest(service=name):
                self.assertEqual(key_list(blocks[name], "cap_drop"), ["ALL"])
        self.assertEqual(key_list(blocks["proxy"], "cap_add"), ["NET_BIND_SERVICE"])


if __name__ == "__main__":
    unittest.main()
