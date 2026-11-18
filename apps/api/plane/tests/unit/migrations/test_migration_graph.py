# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The migration graph stays linear and in step with the models (FORK.md, S15).

An upstream sync adds migrations to `db` and `license` alongside the fork's own;
two branches with the same parent, or two files sharing a number, are the
usual way a merge goes wrong without a conflict marker, and models changed
without a migration ship a schema the code does not match.
"""

from collections import Counter
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.migrations.loader import MigrationLoader
from django.test import override_settings

pytestmark = pytest.mark.unit

# Apps whose migrations live in this repository.
HANGAR_APPS = ("db", "ext", "license")


# The suite runs with --nomigrations, which hides every migration module; these
# tests read the real ones.
REAL_MIGRATIONS = override_settings(MIGRATION_MODULES={})


@pytest.fixture(scope="module")
def loader():
    with REAL_MIGRATIONS:
        return MigrationLoader(None, ignore_no_migrations=True)


@pytest.mark.parametrize("app", HANGAR_APPS)
def test_each_app_has_exactly_one_leaf(loader, app):
    leaves = loader.graph.leaf_nodes(app)
    assert len(leaves) == 1, f"{app} has {len(leaves)} leaf migrations: {leaves}; add a merge or renumber"


@pytest.mark.parametrize("app", HANGAR_APPS)
def test_no_two_migrations_share_a_number(loader, app):
    names = [name for label, name in loader.disk_migrations if label == app]
    assert names, f"no migrations found for {app}"
    duplicates = {number: count for number, count in Counter(name.split("_", 1)[0] for name in names).items() if count > 1}
    assert not duplicates, f"{app} has duplicate migration numbers: {duplicates}"


def test_the_graph_has_no_conflicts(loader):
    conflicts = {app: names for app, names in loader.detect_conflicts().items() if app in HANGAR_APPS}
    assert not conflicts


@pytest.mark.django_db
def test_models_have_no_unmigrated_changes():
    output = StringIO()
    with REAL_MIGRATIONS:
        _make_migrations_check(output)
    assert "No changes detected" in output.getvalue()


def _make_migrations_check(output):
    # --check exits non-zero (SystemExit) when a migration would be written.
    call_command("makemigrations", *HANGAR_APPS, "--check", "--dry-run", stdout=output, stderr=output)
