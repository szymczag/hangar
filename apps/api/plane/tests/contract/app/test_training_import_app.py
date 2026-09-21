# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, IssueType, Project, ProjectMember, State, WorkspaceMember
from plane.ext.capacity.crypto import encrypt_value
from plane.ext.models import (
    GoogleTrainingEventLink,
    GoogleTrainingRule,
    TrainerProfile,
    TrainingEventOccurrence,
    WorkshopSchedule,
    WorkshopSession,
)
from plane.ext.services.issue_types import enable_workshops, ensure_project_system_types
from plane.tests.factories import UserFactory

STARTS = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
WINDOW = {"from": "2026-10-01T00:00:00Z", "to": "2026-12-01T00:00:00Z"}


@pytest.fixture
def keys(settings):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    return settings


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


def _project(workspace, owner, *, members=()):
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=owner)
    ProjectMember.objects.create(project=project, member=owner, workspace=workspace, role=20)
    for member in members:
        ProjectMember.objects.create(project=project, member=member, workspace=workspace, role=15)
    State.objects.create(name="Backlog", project=project, workspace=workspace, group="backlog", default=True)
    ensure_project_system_types(project)
    # A training project opts in to Workshops; importing refuses a project that
    # has not, rather than switching the type on as a side effect.
    enable_workshops(project)
    return project


def _rule(workspace):
    encrypted, key_id = encrypt_value("shared@example.test")
    return GoogleTrainingRule.objects.create(
        workspace=workspace,
        label="Shared training calendar",
        encrypted_calendar_id=encrypted,
        encrypted_organizer=encrypt_value("organizer@example.test")[0],
        encryption_key_id=key_id,
    )


def _occurrence(workspace, user, rule, *, summary="Network security — Acme", key="one", starts=STARTS):
    profile = TrainerProfile.objects.filter(workspace=workspace, user=user).first() or TrainerProfile.objects.create(
        workspace=workspace, user=user
    )
    encrypted, key_id = encrypt_value(summary) if summary else ("", "")
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    return TrainingEventOccurrence.objects.create(
        workspace=workspace,
        trainer=user,
        trainer_profile=profile,
        rule=rule,
        rule_label=rule.label,
        event_key=key,
        calendar_id_hash="hash",
        starts_at=starts,
        ends_at=starts + timedelta(hours=4),
        status=TrainingEventOccurrence.Status.CONFIRMED,
        encrypted_summary=encrypted,
        encryption_key_id=key_id,
        first_seen_at=now,
        last_seen_at=now,
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_a_recognized_training_with_no_work_item_is_offered_for_import(keys, workspace, create_user):
    rule = _rule(workspace)
    _occurrence(workspace, create_user, rule)
    client, _ = _client(create_user)

    response = client.get(f"/api/workspaces/{workspace.slug}/capacity/training-imports/", WINDOW)

    assert response.status_code == status.HTTP_200_OK
    [row] = response.data["results"]
    assert row["title"] == "Network security — Acme"
    assert row["minutes"] == 240
    assert row["status"] == "confirmed"


@pytest.mark.contract
@pytest.mark.django_db
def test_importing_creates_a_workshop_with_its_session_and_links_the_invitation(keys, workspace, create_user):
    """The link is what stops the training being counted twice."""
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["skipped"] == []
    issue = Issue.objects.get(project=project)
    assert issue.name == "Network security — Acme"
    assert issue.type.system_key == IssueType.SystemKey.WORKSHOP
    assert list(issue.issue_assignee.values_list("assignee_id", flat=True)) == [create_user.id]
    session = WorkshopSession.objects.get(schedule=WorkshopSchedule.objects.get(issue=issue))
    assert session.starts_at == STARTS
    link = GoogleTrainingEventLink.objects.get(event_key=occurrence.event_key)
    assert link.session_id == session.id


@pytest.mark.contract
@pytest.mark.django_db
def test_an_imported_training_stops_being_offered(keys, workspace, create_user):
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/training-imports/"
    client.post(
        url,
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert client.get(url, WINDOW).data["results"] == []


@pytest.mark.contract
@pytest.mark.django_db
def test_importing_the_same_training_twice_creates_one_workshop(keys, workspace, create_user):
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/training-imports/"
    payload = {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]}
    client.post(url, payload, format="json", HTTP_X_CSRFTOKEN=csrf)

    second = client.post(url, payload, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert second.data["created"] == []
    assert second.data["skipped"][0]["reason"] == "already_imported"
    assert Issue.objects.filter(project=project).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_a_training_without_a_title_is_named_after_its_rule_and_date(keys, workspace, create_user):
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule, summary="")
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert Issue.objects.get(project=project).name == "Shared training calendar · 2026-11-03"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_trainer_who_cannot_hold_work_here_is_reported_rather_than_left_unassigned(keys, workspace, create_user):
    """Assigning nobody would paper over a decision only a person can make."""
    rule = _rule(workspace)
    outsider = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
    occurrence = _occurrence(workspace, outsider, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.data["created"] == []
    assert response.data["skipped"][0]["reason"] == "trainer_not_in_project"
    assert Issue.objects.filter(project=project).count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_one_bad_row_does_not_sink_the_batch(keys, workspace, create_user):
    rule = _rule(workspace)
    outsider = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=outsider, role=15)
    good = _occurrence(workspace, create_user, rule, key="good")
    bad = _occurrence(workspace, outsider, rule, key="bad")
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(good.id), str(bad.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert len(response.data["created"]) == 1
    assert len(response.data["skipped"]) == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_importing_into_a_project_you_do_not_belong_to_is_refused(keys, workspace, create_user):
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    stranger = UserFactory()
    project = Project.objects.create(name="Other", identifier="OTH", workspace=workspace, created_by=stranger)
    client, csrf = _client(create_user)

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_a_member_cannot_see_calendar_titles_through_this_endpoint(keys, workspace, create_user):
    rule = _rule(workspace)
    _occurrence(workspace, create_user, rule)
    member = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=member, role=15)
    client, _ = _client(member)

    response = client.get(f"/api/workspaces/{workspace.slug}/capacity/training-imports/", WINDOW)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.contract
@pytest.mark.django_db
def test_the_endpoint_is_invisible_while_capacity_is_off(keys, workspace, create_user):
    keys.GOOGLE_CALENDAR_CAPACITY_ENABLED = False
    client, _ = _client(create_user)

    response = client.get(f"/api/workspaces/{workspace.slug}/capacity/training-imports/", WINDOW)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
@pytest.mark.django_db
def test_a_retired_training_cannot_be_imported_from_a_stale_listing(keys, workspace, create_user):
    """An id harvested before the sweep retired it stays usable for the whole
    retention window unless the state is re-checked at import time."""
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)
    TrainingEventOccurrence.objects.filter(pk=occurrence.pk).update(
        state=TrainingEventOccurrence.State.CANCELLED
    )

    response = client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.data["created"] == []
    assert response.data["skipped"][0]["reason"] == "no_longer_active"
    assert Issue.objects.filter(project=project).count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_unlinking_the_invitation_does_not_make_a_training_importable_again(keys, workspace, create_user):
    """Otherwise one unlink turns a single training into two Workshops.

    Unlinking is member-level self-service, so the link's absence cannot be what
    "not imported yet" means.
    """
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/training-imports/"
    payload = {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]}
    client.post(url, payload, format="json", HTTP_X_CSRFTOKEN=csrf)

    GoogleTrainingEventLink.objects.filter(event_key=occurrence.event_key).delete(soft=False)
    second = client.post(url, payload, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert second.data["skipped"][0]["reason"] == "already_imported"
    assert Issue.objects.filter(project=project).count() == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_an_imported_training_records_what_it_became(keys, workspace, create_user):
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    occurrence.refresh_from_db()
    assert occurrence.imported_issue_id == Issue.objects.get(project=project).id


@pytest.mark.contract
@pytest.mark.django_db
def test_deleting_the_work_item_offers_the_training_for_import_again(keys, workspace, create_user):
    """The marker records a decision, not a permanent ban."""
    rule = _rule(workspace)
    occurrence = _occurrence(workspace, create_user, rule)
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/training-imports/"
    client.post(
        url,
        {"project_id": str(project.id), "occurrence_ids": [str(occurrence.id)]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    Issue.objects.filter(project=project).delete(soft=False)
    occurrence.refresh_from_db()

    assert occurrence.imported_issue_id is None
    assert [row["id"] for row in client.get(url, WINDOW).data["results"]] == [str(occurrence.id)]


def _import(client, csrf, workspace, project, occurrence_ids):
    return client.post(
        f"/api/workspaces/{workspace.slug}/capacity/training-imports/",
        {"project_id": str(project.id), "occurrence_ids": [str(value) for value in occurrence_ids]},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_a_training_with_two_trainers_is_listed_once(keys, workspace, create_user):
    """One training, one row, both names on it.

    Each trainer's view of a training is its own record, so a two-trainer
    training used to be listed twice -- which is what invited importing it twice.
    """
    other = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
    rule = _rule(workspace)
    _occurrence(workspace, create_user, rule, key="shared")
    _occurrence(workspace, other, rule, key="shared")
    client, _ = _client(create_user)

    response = client.get(f"/api/workspaces/{workspace.slug}/capacity/training-imports/", WINDOW)

    [row] = response.data["results"]
    assert {trainer["trainer_id"] for trainer in row["trainers"]} == {str(create_user.id), str(other.id)}
    assert len(row["occurrence_ids"]) == 2


@pytest.mark.contract
@pytest.mark.django_db
def test_a_training_with_two_trainers_becomes_one_workshop(keys, workspace, create_user):
    """The defect this grouping exists for.

    Importing both trainers' rows used to create two Workshops for one training,
    each with one trainer. It is one Workshop, one session, both trainers on it,
    and each of them linked to that session so neither is counted twice.
    """
    other = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
    rule = _rule(workspace)
    first = _occurrence(workspace, create_user, rule, key="shared")
    second = _occurrence(workspace, other, rule, key="shared")
    project = _project(workspace, create_user, members=[other])
    client, csrf = _client(create_user)

    response = _import(client, csrf, workspace, project, [first.id, second.id])

    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.data["created"]) == 1
    assert Issue.objects.filter(project=project).count() == 1
    session = WorkshopSession.objects.get()
    assert set(session.trainers.values_list("id", flat=True)) == {create_user.id, other.id}
    assert GoogleTrainingEventLink.objects.filter(session=session).count() == 2


@pytest.mark.contract
@pytest.mark.django_db
def test_selecting_one_trainers_row_imports_the_whole_training(keys, workspace, create_user):
    """Importing half a training would leave the other half to become a second Workshop."""
    other = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
    rule = _rule(workspace)
    first = _occurrence(workspace, create_user, rule, key="shared")
    _occurrence(workspace, other, rule, key="shared")
    project = _project(workspace, create_user, members=[other])
    client, csrf = _client(create_user)

    _import(client, csrf, workspace, project, [first.id])

    session = WorkshopSession.objects.get()
    assert set(session.trainers.values_list("id", flat=True)) == {create_user.id, other.id}


@pytest.mark.contract
@pytest.mark.django_db
def test_a_trainer_added_to_the_project_later_joins_the_existing_workshop(keys, workspace, create_user):
    """The duplication, arriving by the back door.

    The first import takes only the trainer who can hold work in the project and
    leaves the other listed. Once that trainer joins the project, importing again
    must put them on the Workshop that exists -- not create a second one.
    """
    other = UserFactory()
    WorkspaceMember.objects.create(workspace=workspace, member=other, role=15)
    rule = _rule(workspace)
    first = _occurrence(workspace, create_user, rule, key="shared")
    second = _occurrence(workspace, other, rule, key="shared")
    project = _project(workspace, create_user)
    client, csrf = _client(create_user)

    response = _import(client, csrf, workspace, project, [first.id, second.id])
    assert len(response.data["created"]) == 1
    assert {row["reason"] for row in response.data["skipped"]} == {"trainer_not_in_project"}

    ProjectMember.objects.create(project=project, member=other, workspace=workspace, role=15)
    _import(client, csrf, workspace, project, [second.id])

    assert Issue.objects.filter(project=project).count() == 1
    session = WorkshopSession.objects.get()
    assert set(session.trainers.values_list("id", flat=True)) == {create_user.id, other.id}
    assert GoogleTrainingEventLink.objects.filter(session=session).count() == 2
