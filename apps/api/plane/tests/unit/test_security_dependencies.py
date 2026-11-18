# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Libraries the fork's security controls are built on (FORK.md, S7).

Each must be pinned in the project dependencies the production image installs
(pyproject.toml, locked in uv.lock), and importable in the image the tests run
in. A sync that rewrites the manifest and drops one would otherwise fail only
when the feature is first used.
"""

import importlib
import re
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

API_ROOT = Path(__file__).resolve().parents[3]

# distribution name -> import name -> what depends on it
DEPENDENCIES = {
    "python3-saml": ("onelogin.saml2.auth", "SAML 2.0 sign-in"),
    "xmlsec": ("xmlsec", "SAML signature validation"),
    "webauthn": ("webauthn", "God Mode second factor"),
    "python-magic": ("magic", "upload content sniffing"),
    "mistune": ("mistune", "Markdown input rendering"),
    "nh3": ("nh3", "HTML sanitization"),
}


def _normalise(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def _production_pins():
    """Return the exact pins the production image installs: the project
    dependencies plus the `production` group (`uv sync --no-default-groups
    --group production`)."""
    project = tomllib.loads((API_ROOT / "pyproject.toml").read_text())
    specifiers = list(project["project"]["dependencies"])
    specifiers += project["dependency-groups"]["production"]
    pins = {}
    for specifier in specifiers:
        if match := re.match(r"([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==([^\s;]+)", specifier):
            pins[_normalise(match.group(1))] = match.group(3)
    return pins


def _locked_versions():
    lock = tomllib.loads((API_ROOT / "uv.lock").read_text())
    return {_normalise(package["name"]): package.get("version") for package in lock["package"]}


@pytest.mark.parametrize("distribution", sorted(DEPENDENCIES))
def test_is_pinned_in_the_production_dependencies(distribution):
    assert distribution in _production_pins(), (
        f"{distribution} ({DEPENDENCIES[distribution][1]}) is not pinned in the [project] dependencies "
        "or the production group of pyproject.toml"
    )


@pytest.mark.parametrize("distribution", sorted(DEPENDENCIES))
def test_is_locked_at_the_pinned_version(distribution):
    pinned = _production_pins().get(distribution)
    assert _locked_versions().get(distribution) == pinned, (
        f"uv.lock does not hold {distribution}=={pinned}; run `uv lock`"
    )


@pytest.mark.parametrize("distribution", sorted(DEPENDENCIES))
def test_is_importable(distribution):
    module, _purpose = DEPENDENCIES[distribution]
    importlib.import_module(module)


def test_libmagic_is_present_not_only_the_binding():
    magic = importlib.import_module("magic")
    assert magic.from_buffer(b"%PDF-1.4\n", mime=True) == "application/pdf"
