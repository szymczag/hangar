# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The one-off command that takes images on other hosts out of stored fields."""

from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import override_settings

from plane.db.management.commands import localize_external_images as command
from plane.db.models import Project, User

INSTANCE = "https://hangar.example"
STORAGE = "https://files.example"
UNSPLASH = "https://images.unsplash.com/photo-1?w=870"


def run(*args):
    out = StringIO()
    call_command("localize_external_images", *args, stdout=out)
    return out.getvalue()


@pytest.mark.unit
def test_only_absolute_urls_on_other_origins_are_external():
    local = {INSTANCE, STORAGE}
    assert command.is_external(UNSPLASH, local)
    assert command.is_external("https://lh3.googleusercontent.com/a/x", local)
    assert not command.is_external(f"{STORAGE}/uploads/cover.png", local)
    assert not command.is_external(f"{INSTANCE.upper()}/assets/cover.jpg", local)
    assert not command.is_external("/assets/cover.jpg", local)
    assert not command.is_external("", local)
    assert not command.is_external("javascript:alert(1)", local)


@pytest.mark.contract
@pytest.mark.django_db
@override_settings(WEB_URL=INSTANCE, AWS_S3_PUBLIC_ENDPOINT_URL=STORAGE)
def test_report_writes_nothing_and_apply_clears_external_covers(workspace):
    external = Project.objects.create(name="Unsplash", identifier=f"U{uuid4().hex[:4]}", workspace=workspace)
    stored = Project.objects.create(name="Stored", identifier=f"S{uuid4().hex[:4]}", workspace=workspace)
    Project.objects.filter(pk=external.pk).update(cover_image=UNSPLASH)
    Project.objects.filter(pk=stored.pk).update(cover_image=f"{STORAGE}/uploads/cover.png")

    report = run()
    assert "Project.cover_image: 1 external, would be cleared" in report
    assert Project.objects.get(pk=external.pk).cover_image == UNSPLASH

    applied = run("--apply")
    assert "Project.cover_image: 1 external, cleared" in applied
    assert Project.objects.get(pk=external.pk).cover_image is None
    assert Project.objects.get(pk=stored.pk).cover_image == f"{STORAGE}/uploads/cover.png"
    assert "Project.cover_image: 0 external" in run("--apply")


@pytest.mark.contract
@pytest.mark.django_db
@override_settings(WEB_URL=INSTANCE)
def test_an_avatar_that_cannot_be_copied_is_cleared(create_user, monkeypatch):
    User.objects.filter(pk=create_user.pk).update(avatar="https://gitea.example/avatars/1", avatar_asset=None)
    monkeypatch.setattr(command.Command, "_copy_avatar", staticmethod(lambda user: False))

    assert "User.avatar: 1 external, would be copied" in run()
    assert "1 external, 0 copied to storage, 1 cleared" in run("--apply")
    assert User.objects.get(pk=create_user.pk).avatar == ""


@pytest.mark.contract
@pytest.mark.django_db
@override_settings(WEB_URL=INSTANCE)
def test_a_local_origin_given_on_the_command_line_is_kept(workspace):
    project = Project.objects.create(name="Mirror", identifier=f"M{uuid4().hex[:4]}", workspace=workspace)
    Project.objects.filter(pk=project.pk).update(cover_image="https://cdn.hangar.example/cover.png")

    assert "Project.cover_image: 0 external" in run("--apply", "--local-origin", "https://cdn.hangar.example")
    assert Project.objects.get(pk=project.pk).cover_image == "https://cdn.hangar.example/cover.png"
