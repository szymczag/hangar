# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The all-in-one image must carry the API image's runtime packages (S7).

The AIO runner copies the backend's Python site-packages out of the api image,
but not the shared libraries and binaries those packages load at runtime: those
come from the runner's own `apk add`. When the two lists drifted, the AIO image
shipped without libmagic (python-magic then fails on `import magic`, which
breaks upload validation) and without gnupg (the mailer runs `gpg` for OpenPGP
email). This test reads the final stage of both Dockerfiles and requires every
package the api image keeps installed to be installed in the AIO runner too.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
API_DOCKERFILE = REPOSITORY_ROOT / "apps" / "api" / "Dockerfile.api"
AIO_DOCKERFILE = REPOSITORY_ROOT / "deployments" / "aio" / "community" / "Dockerfile"

# Packages the api image installs for good that the AIO runner deliberately does
# not, each with the reason. Keep this list short and justified.
AIO_EXEMPT = {
    # Headers only; the shared library (libffi) cffi needs at runtime is a
    # dependency of the python base image both images start from.
    "libffi-dev": "headers only; libffi ships with the python base image",
}


def final_stage(dockerfile: Path) -> str:
    """The body of the last FROM stage, with line continuations joined."""
    text = dockerfile.read_text()
    text = re.sub(r"\\\n", " ", text)
    # Comment lines inside a continued RUN would otherwise leak into it.
    text = re.sub(r"^\s*#.*$", "", text, flags=re.MULTILINE)
    parts = re.split(r"^FROM\s.*$", text, flags=re.MULTILINE)
    return parts[-1]


def kept_apk_packages(dockerfile: Path) -> set[str]:
    """Package names from every `apk add` in the final stage that stays installed.

    `apk add --virtual <name>` groups are build dependencies removed in the same
    layer, so they are skipped. Version constraints (`bash~=5.3`) are dropped.
    """
    packages: set[str] = set()
    for run in re.findall(r"^\s*RUN\s+(.*)$", final_stage(dockerfile), flags=re.MULTILINE):
        for command in re.split(r"&&|;", run):
            words = command.split()
            if "apk" not in words or "add" not in words:
                continue
            if words.index("add") < words.index("apk"):
                continue
            arguments = words[words.index("add") + 1 :]
            if "--virtual" in arguments or "-t" in arguments:
                continue
            for word in arguments:
                if word.startswith("-"):
                    continue
                name = re.split(r"[~<>=]", word.strip("\"'"), maxsplit=1)[0]
                if name:
                    packages.add(name)
    return packages


class ParserTests(unittest.TestCase):
    def test_finds_the_api_runtime_packages(self):
        packages = kept_apk_packages(API_DOCKERFILE)
        for name in ("libpq", "libmagic", "libxslt", "xmlsec", "gnupg", "bash"):
            self.assertIn(name, packages)

    def test_skips_virtual_build_dependencies(self):
        packages = kept_apk_packages(API_DOCKERFILE)
        for name in ("gcc", "g++", "cargo", "postgresql-dev", "xmlsec-dev"):
            self.assertNotIn(name, packages)

    def test_finds_the_aio_runner_packages(self):
        self.assertIn("libstdc++", kept_apk_packages(AIO_DOCKERFILE))


class AioRuntimePackageTests(unittest.TestCase):
    def test_the_aio_runner_installs_every_api_runtime_package(self):
        missing = kept_apk_packages(API_DOCKERFILE) - kept_apk_packages(AIO_DOCKERFILE) - AIO_EXEMPT.keys()
        self.assertFalse(
            missing,
            f"S7: the AIO runner copies the api's site-packages but not {sorted(missing)}; "
            f"add them to its apk add in {AIO_DOCKERFILE.relative_to(REPOSITORY_ROOT)}, "
            "or exempt them here with the reason",
        )

    def test_exemptions_are_still_needed(self):
        api = kept_apk_packages(API_DOCKERFILE)
        aio = kept_apk_packages(AIO_DOCKERFILE)
        stale = {name for name in AIO_EXEMPT if name not in api or name in aio}
        self.assertFalse(stale, f"stale AIO exemptions: {sorted(stale)}")


if __name__ == "__main__":
    unittest.main()
