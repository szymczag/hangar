# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Unit coverage for the pieces of the project copy service worth isolating.

The endpoint contract tests exercise the whole path; these cover the bits with
their own edge cases -- name and identifier derivation against the partial
unique constraints, the admission caps, and the option normalisation that
decides what a copy is allowed to leave out.
"""

import pytest

from plane.db.models import Project, ProjectMember
from plane.ext.services.project_copy import (
    MAX_MEMBERS,
    CopyPlan,
    ProjectCopyError,
    derive_identifier,
    derive_name,
    duplicate_project,
)

ADMIN = 20


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(name="Base", identifier="BASE", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=ADMIN)
    return project


@pytest.mark.unit
@pytest.mark.django_db
class TestDeriveName:
    def test_first_copy_takes_the_plain_suffix(self, workspace, project):
        assert derive_name(workspace.id, project.name) == "Base (Copy)"

    def test_subsequent_copies_are_numbered(self, workspace, project, create_user):
        Project.objects.create(name="Base (Copy)", identifier="BASE1", workspace=workspace, created_by=create_user)
        assert derive_name(workspace.id, project.name) == "Base (Copy 2)"

    def test_a_soft_deleted_project_does_not_reserve_its_name(self, workspace, project, create_user):
        """The unique constraint is partial on ``deleted_at IS NULL``."""
        taken = Project.objects.create(
            name="Base (Copy)", identifier="BASE1", workspace=workspace, created_by=create_user
        )
        taken.delete()  # soft delete
        assert derive_name(workspace.id, project.name) == "Base (Copy)"

    def test_a_long_name_stays_within_the_column(self, workspace):
        max_length = Project._meta.get_field("name").max_length
        derived = derive_name(workspace.id, "x" * (max_length + 50))
        assert len(derived) <= max_length


@pytest.mark.unit
@pytest.mark.django_db
class TestDeriveIdentifier:
    def test_identifier_is_suffixed_until_free(self, workspace, project):
        assert derive_identifier(workspace.id, project.identifier) == "BASE1"

    def test_identifier_stays_within_the_column(self, workspace):
        max_length = Project._meta.get_field("identifier").max_length
        derived = derive_identifier(workspace.id, "Z" * (max_length + 10))
        assert len(derived) <= max_length

    def test_identifier_is_uppercased(self, workspace):
        assert derive_identifier(workspace.id, "lower") == "LOWER1"


@pytest.mark.unit
class TestCopyPlan:
    def test_structure_cannot_be_switched_off(self):
        """A project without states cannot hold work, so these are not optional."""
        plan = CopyPlan.from_options({"states": False, "work_item_types": False})
        assert plan.states is True
        assert plan.work_item_types is True

    def test_access_granting_options_default_off(self):
        plan = CopyPlan.from_options(None)
        assert plan.members is False
        assert plan.views is False
        assert plan.cycles is False
        assert plan.modules is False

    def test_structural_defaults_stay_on(self):
        plan = CopyPlan.from_options(None)
        assert plan.labels is True
        assert plan.estimates is True
        assert plan.intake is True

    def test_unknown_keys_are_ignored_rather_than_crashing(self):
        """The serializer rejects them; the service must not blow up either."""
        assert CopyPlan.from_options({"nonsense": True}).labels is True


@pytest.mark.unit
@pytest.mark.django_db
class TestAdmission:
    def test_an_archived_source_is_refused(self, project, create_user):
        from django.utils import timezone

        project.archived_at = timezone.now()
        project.save()

        with pytest.raises(ProjectCopyError) as error:
            duplicate_project(source=project, actor=create_user)

        assert error.value.code == "PROJECT_ARCHIVED"

    def test_too_many_members_is_refused_rather_than_run_synchronously(
        self, project, workspace, create_user, monkeypatch
    ):
        """The cap is the seam where an async job would take over."""
        monkeypatch.setattr("plane.ext.services.project_copy.MAX_MEMBERS", 0)

        with pytest.raises(ProjectCopyError) as error:
            duplicate_project(source=project, actor=create_user, options={"members": True})

        assert error.value.code == "PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY"
        # Only the limit that was exceeded -- the per-model tally would report
        # how many rows the source holds, including ones this caller cannot see.
        assert error.value.detail == {"limit": "members"}

    def test_the_cap_is_a_real_number(self):
        assert MAX_MEMBERS > 0
