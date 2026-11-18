# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import re
from collections import Counter
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.core.management.commands import makemigrations as django_makemigrations
from django.db.migrations.loader import MigrationLoader
from django.test import override_settings

from plane.db.management.commands import makemigrations
from plane.db.management.commands.makemigrations import mismatches, parse, render

pytestmark = pytest.mark.unit

LEAVES = {"license": "0005_issue_description", "db": "0193_trash"}
STALE = {"license": "0005_issue_description", "db": "0192_old"}


@pytest.fixture
def lockfile(tmp_path):
    # Django's own makemigrations is stubbed out: these tests cover only what
    # the override adds. pytest runs with --nomigrations, so the real
    # migration graph is not available here; CI checks it on every PR.
    path = tmp_path / "migrations_lockfile.txt"
    with (
        patch.object(django_makemigrations.Command, "handle", return_value=None),
        patch.object(makemigrations, "plane_leaves", return_value=LEAVES),
        patch.object(makemigrations, "LOCKFILE", path),
    ):
        yield path


def run(**options):
    stderr = StringIO()
    call_command("makemigrations", stderr=stderr, **options)
    return stderr.getvalue()


def test_check_passes_when_lockfile_matches(lockfile):
    lockfile.write_text(render(LEAVES))
    assert run(check_changes=True, dry_run=True) == ""


def test_check_exits_2_when_lockfile_is_stale(lockfile):
    lockfile.write_text(render(STALE))
    with pytest.raises(SystemExit) as exit_info:
        run(check_changes=True, dry_run=True)
    assert exit_info.value.code == 2


def test_check_exits_2_when_lockfile_is_missing(lockfile):
    with pytest.raises(SystemExit) as exit_info:
        run(check_changes=True, dry_run=True)
    assert exit_info.value.code == 2


def test_check_reports_conflict_markers_and_exits_2(lockfile):
    lockfile.write_text(render(LEAVES) + "<<<<<<< HEAD\nlicense: 0007_a\n=======\nlicense: 0007_b\n>>>>>>> branch\n")
    stderr = StringIO()
    with pytest.raises(SystemExit) as exit_info:
        call_command("makemigrations", check_changes=True, dry_run=True, stderr=stderr)
    assert exit_info.value.code == 2
    assert "conflict markers" in stderr.getvalue()


def test_warn_only_reports_a_stale_lockfile_without_failing(lockfile):
    lockfile.write_text(render(STALE))
    assert "db: lockfile has 0192_old, graph has 0193_trash" in run(
        check_changes=True, dry_run=True, lockfile_warn_only=True
    )


def test_plain_run_writes_the_lockfile(lockfile):
    run()
    assert parse(lockfile.read_text()) == LEAVES


def test_dry_run_does_not_write_the_lockfile(lockfile):
    run(dry_run=True)
    assert not lockfile.exists()


def test_parse_skips_malformed_lines():
    assert parse("license 0005_issue_description\ndb: 0193_trash\n") == {"db": "0193_trash"}


def test_render_round_trips_through_parse():
    assert parse(render(LEAVES)) == LEAVES


def test_render_separates_apps_with_blank_lines():
    # Git conflicts on adjacent lines, so two PRs touching different apps
    # would conflict if their lines touched.
    assert "db: 0193_trash\n\nlicense: 0005_issue_description\n" in render(LEAVES)


def test_parse_ignores_comments_and_blank_lines():
    text = "# note: not an app\n#\n\ndb: 0193_trash\n\n"
    assert parse(text) == {"db": "0193_trash"}


def test_mismatches_names_changed_missing_and_extra_apps():
    locked = {"db": "0192_old", "license": "0005_issue_description", "space": "0001_gone"}
    leaves = {"db": "0193_trash", "license": "0005_issue_description", "web": "0007_new"}
    assert mismatches(locked, leaves) == [
        "db: lockfile has 0192_old, graph has 0193_trash",
        "space: lockfile has 0001_gone, graph has nothing",
        "web: lockfile has nothing, graph has 0007_new",
    ]


def test_missing_lockfile_reports_every_app():
    assert mismatches({}, LEAVES) == [
        "db: lockfile has nothing, graph has 0193_trash",
        "license: lockfile has nothing, graph has 0005_issue_description",
    ]


# Hangar: the checks below read the real migration files. The tests above stub
# the graph out, so on their own they would pass with a lockfile that names a
# migration that no longer exists, an app missing from it, or two migrations
# competing for one number. Hangar carries upstream migrations under its own
# numbers (upstream db 0123-0125 are 0135/0136/0134 here), so a sync that brings
# upstream's files back in must fail here rather than in a deployment.

MIGRATION_NAME = re.compile(r"^(?P<number>\d{4})_\w+\.py$")


def migration_files_by_app():
    found = {}
    for config in django_apps.get_app_configs():
        if not config.name.startswith("plane."):
            continue
        directory = Path(config.path) / "migrations"
        names = sorted(path.name for path in directory.glob("*.py") if MIGRATION_NAME.match(path.name))
        if names:
            found[config.label] = names
    return found


def duplicate_numbers(names):
    numbers = Counter(MIGRATION_NAME.match(name)["number"] for name in names)
    return sorted(number for number, count in numbers.items() if count > 1)


def apps_with_several_leaves(leaf_nodes):
    counts = Counter(app for app, _ in leaf_nodes)
    return sorted(app for app, count in counts.items() if count > 1)


@pytest.fixture
def real_graph():
    # pytest runs with --nomigrations, which points MIGRATION_MODULES at
    # nothing; an empty mapping puts every app's own migrations back.
    with override_settings(MIGRATION_MODULES={}):
        yield MigrationLoader(None, ignore_no_migrations=True).graph


def test_committed_lockfile_matches_the_migration_graph():
    assert makemigrations.LOCKFILE.exists(), f"{makemigrations.LOCKFILE} is missing"
    text = makemigrations.LOCKFILE.read_text()
    assert "<<<<<<<" not in text
    with override_settings(MIGRATION_MODULES={}):
        leaves = makemigrations.plane_leaves()
    assert mismatches(parse(text), leaves) == []


def test_committed_lockfile_names_every_plane_app_with_migrations():
    assert set(parse(makemigrations.LOCKFILE.read_text())) == set(migration_files_by_app())


def test_every_plane_app_has_exactly_one_leaf_migration(real_graph):
    plane_labels = set(migration_files_by_app())
    leaves = [(app, name) for app, name in real_graph.leaf_nodes() if app in plane_labels]
    assert apps_with_several_leaves(leaves) == []
    assert {app for app, _ in leaves} == plane_labels


def test_no_two_migrations_of_an_app_share_a_number():
    assert {app: dup for app, names in migration_files_by_app().items() if (dup := duplicate_numbers(names))} == {}


def test_duplicate_numbers_finds_a_reintroduced_upstream_migration():
    names = [
        "0123_email_delivery_audit_receipts.py",
        "0123_remove_apitoken_is_service_and_allowed_rate_limit.py",
        "0124_federated_sso_identity.py",
    ]
    assert duplicate_numbers(names) == ["0123"]


def test_apps_with_several_leaves_finds_a_forked_chain():
    leaves = [("db", "0136_a"), ("db", "0125_b"), ("license", "0024_c")]
    assert apps_with_several_leaves(leaves) == ["db"]
