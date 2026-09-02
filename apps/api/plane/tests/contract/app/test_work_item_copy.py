# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Copying a project's work items.

The interesting failures here are all silent ones. ``bulk_create`` bypasses
``Issue.save()``, so a field nobody sets is simply wrong rather than missing;
``auto_now_add`` overwrites the dates a copy is supposed to preserve without
complaining; nothing enforces uniqueness on ``(project, sequence)``, so two work
items can end up numbered alike with no error anywhere; and a relation copied
one-sidedly points into another project and renders as a link its reader cannot
open. Each of those has a test here, and each of them passes today only because
of a specific line that would be easy to remove.
"""

import uuid

import pytest
from django.core.cache import cache
from rest_framework import status

from plane.db.models import (
    Cycle,
    CycleIssue,
    Issue,
    IssueAssignee,
    IssueLabel,
    IssueLink,
    IssueRelation,
    IssueSequence,
    Label,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)
from plane.ext.models import ProjectCopyJob
from plane.ext.services import work_item_copy
from plane.ext.services.issue_types import ensure_project_system_types
from plane.ext.tasks import copy_project_work_items

ADMIN = 20
MEMBER = 15


def duplicate_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/duplicate/"


def status_url(slug, project_id):
    return f"/api/workspaces/{slug}/projects/{project_id}/copy-status/"


@pytest.fixture(autouse=True)
def clear_throttles():
    """The endpoint is throttled per user and per workspace, and these tests
    share one slug."""
    cache.clear()


@pytest.fixture
def source(db, workspace, create_user):
    """A project with a small but awkward set of work items."""
    project = Project.objects.create(name="Source", identifier="SRC", workspace=workspace, created_by=create_user)
    ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=ADMIN)
    ensure_project_system_types(project)

    backlog = State.objects.create(
        name="Backlog", color="#000", group="backlog", project=project, workspace=workspace, sequence=1000
    )
    label = Label.objects.create(name="Area", project=project, workspace=workspace, sort_order=1)
    cycle = Cycle.objects.create(name="Sprint 1", owned_by=create_user, project=project, workspace=workspace)

    parent = Issue.objects.create(
        name="Parent", project=project, workspace=workspace, state=backlog, created_by=create_user
    )
    child = Issue.objects.create(
        name="Child", project=project, workspace=workspace, state=backlog, parent=parent, created_by=create_user
    )
    Issue.objects.create(
        name="Grandchild", project=project, workspace=workspace, state=backlog, parent=child, created_by=create_user
    )

    IssueLabel.objects.create(issue=parent, label=label, project=project, workspace=workspace)
    IssueLink.objects.create(
        issue=parent, url="https://example.invalid/spec", title="Spec", project=project, workspace=workspace
    )
    CycleIssue.objects.create(issue=parent, cycle=cycle, project=project, workspace=workspace)

    project.default_state = backlog
    project.save()
    return project


def _duplicate(client, workspace, source, **include):
    body = {"include": {"work_items": True, **include}}
    return client.post(duplicate_url(workspace.slug, source.id), body, format="json")


def _run_job(copy_id):
    job = ProjectCopyJob.objects.get(target_project_id=copy_id)
    copy_project_work_items(str(job.id))
    job.refresh_from_db()
    return job


@pytest.mark.contract
@pytest.mark.django_db
def test_the_copy_is_created_before_any_work_item_is(session_client, workspace, source):
    """The project must be usable immediately; the items arrive after."""
    response = _duplicate(session_client, workspace, source)

    assert response.status_code == status.HTTP_201_CREATED, response.data
    copy_id = response.data["id"]
    assert response.data["copy_summary"]["work_items"]["status"] == "queued"
    assert response.data["copy_summary"]["work_items"]["total"] == 3
    assert not Issue.objects.filter(project_id=copy_id).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_the_sub_item_tree_is_rebuilt_inside_the_copy(session_client, workspace, source):
    """The two-pass parent remap, and the thing it exists to prevent."""
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    _run_job(copy_id)

    copied = {issue.name: issue for issue in Issue.objects.filter(project_id=copy_id)}
    assert copied["Parent"].parent_id is None
    assert copied["Child"].parent_id == copied["Parent"].id
    assert copied["Grandchild"].parent_id == copied["Child"].id

    # A parent pointing back into the source would be a cross-project foreign
    # key: a member of the copy would see a sub-item they cannot open.
    source_ids = set(Issue.objects.filter(project=source).values_list("id", flat=True))
    assert not any(issue.parent_id in source_ids for issue in copied.values())


@pytest.mark.contract
@pytest.mark.django_db
def test_work_item_numbers_and_their_sequence_rows_travel(session_client, workspace, source):
    """`(project, sequence_id)` is the source-to-copy key, so it must be exact."""
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    _run_job(copy_id)

    source_numbers = sorted(Issue.objects.filter(project=source).values_list("sequence_id", flat=True))
    copy_numbers = sorted(Issue.objects.filter(project_id=copy_id).values_list("sequence_id", flat=True))
    assert copy_numbers == source_numbers

    for issue in Issue.objects.filter(project_id=copy_id):
        rows = IssueSequence.objects.filter(issue=issue)
        assert rows.count() == 1, "exactly one sequence row per work item"
        assert rows.first().sequence == issue.sequence_id


@pytest.mark.contract
@pytest.mark.django_db
def test_a_work_item_created_during_the_copy_cannot_take_a_reserved_number(session_client, workspace, source):
    """The silent collision the reservation sentinel exists to prevent.

    Nothing enforces uniqueness on ``(project, sequence)``, so without the
    reservation this produces two work items numbered alike and raises nothing.
    """
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    copy = Project.objects.get(pk=copy_id)

    # Somebody adds an item to the copy while the job is still queued.
    interloper = Issue.objects.create(
        name="Added by hand", project=copy, workspace=workspace, created_by=copy.created_by
    )
    assert interloper.sequence_id > 3, "must land above everything the copy still owes"

    _run_job(copy_id)

    numbers = list(Issue.objects.filter(project_id=copy_id).values_list("sequence_id", flat=True))
    assert len(numbers) == len(set(numbers)), "no two work items may share a number"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_original_author_and_dates_are_preserved(session_client, workspace, source, create_user):
    """`auto_now_add` overwrites both on insert; only the second pass restores
    them."""
    author = User.objects.create(email="author@corp.example", username=uuid.uuid4().hex)
    original = Issue.objects.filter(project=source, name="Parent").first()
    Issue.objects.filter(pk=original.pk).update(created_by=author)

    copy_id = _duplicate(session_client, workspace, source).data["id"]
    _run_job(copy_id)

    original.refresh_from_db()
    copied = Issue.objects.get(project_id=copy_id, name="Parent")
    assert copied.created_by_id == author.id, "the source's author, not whoever copied"
    assert copied.created_at == original.created_at
    assert copied.updated_at == original.updated_at


@pytest.mark.contract
@pytest.mark.django_db
def test_every_copied_work_item_belongs_to_the_new_workspace(session_client, workspace, source):
    """`bulk_create` bypasses the `save()` that normally derives `workspace`."""
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    _run_job(copy_id)

    for issue in Issue.objects.filter(project_id=copy_id):
        assert issue.workspace_id == workspace.id
        assert issue.project_id == uuid.UUID(str(copy_id))
        assert issue.description_stripped is not None or not issue.description_html


@pytest.mark.contract
@pytest.mark.django_db
def test_external_identifiers_are_cleared(session_client, workspace, source):
    """`todoist_issue_external_uidx` would otherwise let a re-import skip rows."""
    # Distinct ids per row: that same partial unique constrains the source too.
    for index, issue in enumerate(Issue.objects.filter(project=source)):
        Issue.objects.filter(pk=issue.pk).update(external_source="todoist_csv", external_id=f"task-{index}")

    copy_id = _duplicate(session_client, workspace, source).data["id"]
    _run_job(copy_id)

    assert not Issue.objects.filter(project_id=copy_id).exclude(external_source=None).exists()
    assert not Issue.objects.filter(project_id=copy_id).exclude(external_id=None).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_an_assignee_who_is_not_in_the_copy_is_dropped_and_counted(session_client, workspace, source, create_user):
    outsider = User.objects.create(email="outsider@corp.example", username=uuid.uuid4().hex)
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=MEMBER)
    ProjectMember.objects.create(project=source, member=outsider, workspace=workspace, role=MEMBER)
    parent = Issue.objects.get(project=source, name="Parent")
    IssueAssignee.objects.create(issue=parent, assignee=outsider, project=source, workspace=workspace)
    IssueAssignee.objects.create(issue=parent, assignee=create_user, project=source, workspace=workspace)

    # Members are not copied, so only the person doing the copy is in the target.
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    job = _run_job(copy_id)

    copied_parent = Issue.objects.get(project_id=copy_id, name="Parent")
    assignees = set(IssueAssignee.objects.filter(issue=copied_parent).values_list("assignee_id", flat=True))
    assert assignees == {create_user.id}
    assert job.counts.get("assignees_dropped") == 1
    assert "work_items:assignees-not-in-copy" in job.skipped


@pytest.mark.contract
@pytest.mark.django_db
def test_cycle_membership_is_not_copied_unless_cycles_are(session_client, workspace, source):
    """Copying it anyway would carry other people's sprint planning across."""
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    job = _run_job(copy_id)

    assert not CycleIssue.objects.filter(project_id=copy_id).exists()
    assert "work_items:cycles-not-copied" in job.skipped


@pytest.mark.contract
@pytest.mark.django_db
def test_cycle_membership_travels_when_cycles_are_copied(session_client, workspace, source):
    copy_id = _duplicate(session_client, workspace, source, cycles=True).data["id"]
    _run_job(copy_id)

    membership = CycleIssue.objects.filter(project_id=copy_id)
    assert membership.count() == 1
    # The membership must point at the copy's cycle, not the source's.
    assert membership.first().cycle.project_id == uuid.UUID(str(copy_id))


@pytest.mark.contract
@pytest.mark.django_db
def test_a_relation_with_one_end_outside_the_copy_is_dropped(session_client, workspace, source, create_user):
    """Both ends are plain FKs to Issue, so a one-sided copy leaks across
    projects."""
    other = Project.objects.create(name="Other", identifier="OTH", workspace=workspace, created_by=create_user)
    ensure_project_system_types(other)
    outside = Issue.objects.create(name="Elsewhere", project=other, workspace=workspace, created_by=create_user)

    parent = Issue.objects.get(project=source, name="Parent")
    child = Issue.objects.get(project=source, name="Child")
    IssueRelation.objects.create(
        issue=parent, related_issue=child, relation_type="blocked_by", project=source, workspace=workspace
    )
    IssueRelation.objects.create(
        issue=parent, related_issue=outside, relation_type="blocked_by", project=source, workspace=workspace
    )

    copy_id = _duplicate(session_client, workspace, source).data["id"]
    job = _run_job(copy_id)

    relations = IssueRelation.objects.filter(project_id=copy_id)
    assert relations.count() == 1
    assert relations.first().related_issue.project_id == uuid.UUID(str(copy_id))
    assert job.counts.get("relations_dropped") == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_a_resumed_copy_adds_the_remainder_and_never_a_duplicate(session_client, workspace, source):
    """The whole resume design, exercised by running the job twice.

    The second run must find its work already done and add nothing -- which is
    what a redispatch after a killed worker looks like.
    """
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    _run_job(copy_id)
    first = list(Issue.objects.filter(project_id=copy_id).values_list("id", flat=True))

    job = ProjectCopyJob.objects.get(target_project_id=copy_id)
    job.status = ProjectCopyJob.Status.QUEUED
    job.completed_at = None
    job.save(update_fields=["status", "completed_at"])
    copy_project_work_items(str(job.id))

    second = list(Issue.objects.filter(project_id=copy_id).values_list("id", flat=True))
    assert sorted(second) == sorted(first), "a rerun must not create a second copy"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_partial_copy_is_completed_rather_than_duplicated(session_client, workspace, source):
    """Half the work items already present, as a killed worker would leave."""
    copy_id = _duplicate(session_client, workspace, source).data["id"]
    copy = Project.objects.get(pk=copy_id)
    job = ProjectCopyJob.objects.get(target_project_id=copy_id)

    # Copy one batch by hand, then let the job carry on.
    one = list(work_item_copy.source_work_items(source.id)[:1])
    work_item_copy.copy_issue_batch(
        sources=one,
        target_project=copy,
        remap=work_item_copy.StoredRemap(job.remap),
        type_ids=work_item_copy._available_type_ids(copy),
    )
    assert Issue.objects.filter(project_id=copy_id).count() == 1

    _run_job(copy_id)

    numbers = list(Issue.objects.filter(project_id=copy_id).values_list("sequence_id", flat=True))
    assert sorted(numbers) == [1, 2, 3]
    assert len(numbers) == len(set(numbers))


@pytest.mark.contract
@pytest.mark.django_db
def test_no_work_items_are_copied_unless_they_are_asked_for(session_client, workspace, source):
    response = session_client.post(duplicate_url(workspace.slug, source.id), {}, format="json")

    copy_id = response.data["id"]
    assert not Issue.objects.filter(project_id=copy_id).exists()
    assert not ProjectCopyJob.objects.filter(target_project_id=copy_id).exists()
    assert "work_items" not in response.data["copy_summary"]
    assert "work_items:not-copied" in response.data["copy_summary"]["skipped"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_second_copy_is_refused_while_one_is_running(session_client, workspace, source):
    """One work item copy per workspace: the defence against queueing ten."""
    _duplicate(session_client, workspace, source)

    second = _duplicate(session_client, workspace, source)

    assert second.status_code == status.HTTP_409_CONFLICT
    assert second.data["error"] == "PROJECT_COPY_ALREADY_RUNNING"


@pytest.mark.contract
@pytest.mark.django_db
def test_progress_is_readable_from_the_project_the_client_is_looking_at(session_client, workspace, source):
    copy_id = _duplicate(session_client, workspace, source).data["id"]

    queued = session_client.get(status_url(workspace.slug, copy_id))
    assert queued.status_code == status.HTTP_200_OK
    assert queued.data["job"]["status"] == "queued"
    assert queued.data["job"]["total"] == 3

    _run_job(copy_id)

    done = session_client.get(status_url(workspace.slug, copy_id))
    assert done.data["job"]["status"] == "completed"
    assert done.data["job"]["copied"] == 3


@pytest.mark.contract
@pytest.mark.django_db
def test_a_project_that_was_never_copied_reports_no_job(session_client, workspace, source):
    response = session_client.get(status_url(workspace.slug, source.id))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["job"] is None
