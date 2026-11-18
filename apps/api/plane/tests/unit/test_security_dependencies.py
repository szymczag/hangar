# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Libraries the fork's security controls are built on (FORK.md, S7).

Each must be declared in the requirement manifests the production image
installs, and importable in the image the tests run in. A sync that rewrites a
manifest and drops one would otherwise fail only when the feature is first used.
"""

import importlib
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REQUIREMENTS = Path(__file__).resolve().parents[3] / "requirements"

# distribution name -> import name -> what depends on it
DEPENDENCIES = {
    "python3-saml": ("onelogin.saml2.auth", "SAML 2.0 sign-in"),
    "xmlsec": ("xmlsec", "SAML signature validation"),
    "webauthn": ("webauthn", "God Mode second factor"),
    "python-magic": ("magic", "upload content sniffing"),
    "mistune": ("mistune", "Markdown input rendering"),
    "nh3": ("nh3", "HTML sanitization"),
}


def _production_requirements(name="production.txt", seen=None):
    """Return the pinned distributions production.txt installs, following -r."""
    seen = set() if seen is None else seen
    if name in seen:
        return {}
    seen.add(name)
    pins = {}
    for line in (REQUIREMENTS / name).read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line.startswith("-r "):
            pins.update(_production_requirements(line[3:].strip(), seen))
        elif match := re.match(r"([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==(\S+)", line):
            pins[match.group(1).lower()] = match.group(3)
    return pins


@pytest.mark.parametrize("distribution", sorted(DEPENDENCIES))
def test_is_pinned_in_the_production_requirements(distribution):
    assert distribution in _production_requirements(), (
        f"{distribution} ({DEPENDENCIES[distribution][1]}) is not pinned in requirements/production.txt "
        "or a file it includes"
    )


@pytest.mark.parametrize("distribution", sorted(DEPENDENCIES))
def test_is_importable(distribution):
    module, _purpose = DEPENDENCIES[distribution]
    importlib.import_module(module)


def test_libmagic_is_present_not_only_the_binding():
    magic = importlib.import_module("magic")
    assert magic.from_buffer(b"%PDF-1.4\n", mime=True) == "application/pdf"
