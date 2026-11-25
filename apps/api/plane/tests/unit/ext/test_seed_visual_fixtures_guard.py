# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The visual seed refuses to run unless the environment opts in.

It gives its users the published password "visual-regression", so running it
against a real database would leave accounts with known credentials.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from plane.db.models import User, Workspace
from plane.ext.management.commands.seed_visual_fixtures import OPT_IN_VARIABLE


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.parametrize("value", [None, "", "0", "true", "yes"])
def test_refuses_without_explicit_opt_in_and_writes_nothing(monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv(OPT_IN_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(OPT_IN_VARIABLE, value)
    manifest = tmp_path / "vr" / "fixtures.json"
    users_before = User.objects.count()
    workspaces_before = Workspace.objects.count()

    with pytest.raises(CommandError, match=OPT_IN_VARIABLE):
        call_command("seed_visual_fixtures", "--out", str(manifest))

    assert User.objects.count() == users_before
    assert Workspace.objects.count() == workspaces_before
    assert not User.objects.filter(email__endswith="@hangar.test").exists()
    assert not manifest.exists()
    assert not manifest.parent.exists()
