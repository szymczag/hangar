# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import csv
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import Issue, Project, ProjectMember, State
from plane.ext.capacity.crypto import encrypt_value
from plane.ext.models import (
    GoogleTrainingEventLink,
    GoogleTrainingRule,
    TrainerProfile,
    TrainerTrainingSyncState,
    TrainingCalendarSyncState,
    TrainingEventOccurrence,
    WorkshopSchedule,
    WorkshopSession,
)
from plane.ext.services.issue_types import ensure_project_workshop_type
from plane.tests.factories import UserFactory

OCTOBER = {"from": "2026-10-01T00:00:00Z", "to": "2026-11-01T00:00:00Z"}
STARTS = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
URL = "/api/workspaces/{slug}/capacity/training-report/"


@pytest.fixture
def keys(settings):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    return settings


def _client(user):
    client = APIClient()
    client.force_login(user)
    return client


def _profile(workspace, user, *, consent="ok", synced=True):
    profile = TrainerProfile.objects.create(workspace=workspace, user=user)
    if synced:
        TrainerTrainingSyncState.objects.create(
            trainer_profile=profile,
            consent_state=consent,
            last_materialized_at=datetime.now(timezone.utc),
        )
    return profile


def _rule_with_state(workspace, *, last_success_at):
    encrypted, key_id = encrypt_value("shared@example.test")
    rule = GoogleTrainingRule.objects.create(
        workspace=workspace,
        label="Shared training calendar",
        encrypted_calendar_id=encrypted,
        encrypted_organizer=encrypt_value("organizer@example.test")[0],
        encryption_key_id=key_id,
    )
    TrainingCalendarSyncState.objects.create(
        workspace=workspace,
        rule=rule,
        window_starts_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        window_ends_at=datetime(2027, 5, 1, tzinfo=timezone.utc),
        last_success_at=last_success_at,
        last_full_scan_at=last_success_at,
    )
    return rule


def _occurrence(workspace, user, profile, rule, *, key="one", starts=STARTS, hours=4, status_="confirmed"):
    return TrainingEventOccurrence.objects.create(
        workspace=workspace,
        trainer=user,
        trainer_profile=profile,
        rule=rule,
        rule_label=rule.label,
        event_key=key,
        calendar_id_hash="hash",
        starts_at=starts,
        ends_at=starts + timedelta(hours=hours),
        status=status_,
        first_seen_at=starts,
        last_seen_at=starts,
    )


def _delivered_session(workspace, user, *, starts=STARTS, hours=3):
    project = Project.objects.create(name="Training", identifier="TRN", workspace=workspace, created_by=user)
    ProjectMember.objects.create(project=project, member=user, workspace=workspace, role=20)
    State.objects.create(name="Backlog", project=project, workspace=workspace, group="backlog", default=True)
    issue = Issue.objects.create(
        name="Delivered workshop",
        project=project,
        workspace=workspace,
        type=ensure_project_workshop_type(project),
        created_by=user,
    )
    schedule = WorkshopSchedule.objects.create(issue=issue, starts_at=starts, ends_at=starts + timedelta(hours=hours))
    session = WorkshopSession.objects.create(
        schedule=schedule, position=0, starts_at=starts, ends_at=starts + timedelta(hours=hours)
    )
    session.trainers.add(user)
    return session


@pytest.mark.contract
@pytest.mark.django_db
def test_the_report_answers_a_month_without_asking_google(keys, workspace, create_user, monkeypatch):
    """The entire reason the occurrence table exists."""
    exploding = MagicMock(side_effect=AssertionError("the report must not call Google"))
    monkeypatch.setattr("plane.ext.capacity.calculation._google_client", exploding)
    profile = _profile(workspace, create_user)
    rule = _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))
    _occurrence(workspace, create_user, profile, rule)

    response = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER)

    assert response.status_code == status.HTTP_200_OK
    exploding.assert_not_called()
    [row] = response.data["trainers"]
    assert row["external_confirmed_sessions"] == 1
    assert row["external_confirmed_minutes"] == 240


@pytest.mark.contract
@pytest.mark.django_db
def test_a_month_is_allowed_where_the_ledger_caps_at_a_fortnight(keys, workspace, create_user):
    _profile(workspace, create_user)

    response = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unreasonable_range_is_refused(keys, workspace, create_user):
    response = _client(create_user).get(
        URL.format(slug=workspace.slug), {"from": "2020-01-01T00:00:00Z", "to": "2026-01-01T00:00:00Z"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
@pytest.mark.django_db
def test_delivered_and_external_training_are_reported_side_by_side(keys, workspace, create_user):
    profile = _profile(workspace, create_user)
    rule = _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))
    _occurrence(workspace, create_user, profile, rule)
    _delivered_session(workspace, create_user, starts=STARTS + timedelta(days=2))

    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]

    assert row["session_count"] == 1
    assert row["delivery_minutes"] == 180
    assert row["external_confirmed_minutes"] == 240


@pytest.mark.contract
@pytest.mark.django_db
def test_a_training_already_linked_to_a_session_is_not_counted_twice(keys, workspace, create_user):
    """The rule the ledger and the report have to agree on."""
    profile = _profile(workspace, create_user)
    rule = _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))
    occurrence = _occurrence(workspace, create_user, profile, rule)
    session = _delivered_session(workspace, create_user, starts=STARTS, hours=4)
    GoogleTrainingEventLink.objects.create(
        workspace=workspace, trainer=create_user, event_key=occurrence.event_key, session=session
    )

    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]

    assert row["delivery_minutes"] == 240
    assert row["external_confirmed_sessions"] == 0, "linked training is Hangar delivery, not external"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_trainer_whose_consent_lapsed_is_marked_and_left_out_of_totals(keys, workspace, create_user):
    """Rendering them as a zero would be a quiet lie in a staffing document."""
    _profile(workspace, create_user, consent="consent_missing")
    _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))

    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]

    assert row["sync_status"] == "consent_missing"
    assert row["counts_towards_totals"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_trainer_never_swept_is_distinguishable_from_one_who_ran_nothing(keys, workspace, create_user):
    _profile(workspace, create_user, synced=False)

    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]

    assert row["sync_status"] == "never_synced"
    assert row["counts_towards_totals"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_the_report_says_how_fresh_it_is(keys, workspace, create_user):
    _profile(workspace, create_user)
    swept_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    _rule_with_state(workspace, last_success_at=swept_at)

    data = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data

    assert data["data_as_of"] is not None
    assert data["coverage"]["calendars"][0]["status"] == "ok"
    assert data["coverage"]["requested_range_covered"] is True


@pytest.mark.contract
@pytest.mark.django_db
def test_a_calendar_nobody_has_swept_in_hours_is_reported_as_stale(keys, workspace, create_user):
    _profile(workspace, create_user)
    _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc) - timedelta(hours=6))

    data = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data

    assert data["coverage"]["calendars"][0]["status"] == "stale"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_range_outside_the_swept_window_is_flagged(keys, workspace, create_user):
    _profile(workspace, create_user)
    _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))

    data = _client(create_user).get(
        URL.format(slug=workspace.slug), {"from": "2025-01-01T00:00:00Z", "to": "2025-02-01T00:00:00Z"}
    ).data

    assert data["coverage"]["requested_range_covered"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_the_csv_is_downloadable_and_safe_to_open(keys, workspace, create_user):
    """`export`, not `format`: DRF reserves the latter and answers 404 for it."""
    user = UserFactory(display_name="=cmd|calc")
    TrainerProfile.objects.create(workspace=workspace, user=user)
    _profile(workspace, create_user)

    response = _client(create_user).get(URL.format(slug=workspace.slug), {**OCTOBER, "export": "csv"})

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "text/csv"
    assert "attachment; filename=" in response["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(response.content.decode())))
    assert rows[0][0] == "Trainer"
    names = [row[0] for row in rows[1:]]
    assert "'=cmd|calc" in names, "a formula-looking name must be neutralized"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_report_is_invisible_while_capacity_is_off(keys, workspace, create_user):
    keys.GOOGLE_CALENDAR_CAPACITY_ENABLED = False

    response = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER)

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.contract
@pytest.mark.django_db
def test_a_trainer_whose_sweep_has_frozen_is_not_reported_as_fully_counted(keys, workspace, create_user):
    """Consent alone does not mean the numbers are current.

    A calendar stuffed past the event ceiling fails every pass and the backoff
    retries into the same wall. Reading only `consent_state` reported those
    trainers as counted, which is the one thing a staffing document must not do.
    """
    profile = _profile(workspace, create_user)
    TrainerTrainingSyncState.objects.filter(trainer_profile=profile).update(
        last_materialized_at=datetime.now(timezone.utc) - timedelta(hours=9)
    )
    _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc) - timedelta(hours=9))

    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]

    assert row["sync_status"] == "stale"
    assert row["counts_towards_totals"] is False


@pytest.mark.contract
@pytest.mark.django_db
def test_a_recently_swept_trainer_counts(keys, workspace, create_user):
    profile = _profile(workspace, create_user)
    TrainerTrainingSyncState.objects.filter(trainer_profile=profile).update(
        last_materialized_at=datetime.now(timezone.utc) - timedelta(minutes=10)
    )
    _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))

    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]

    assert row["sync_status"] == "ok"
    assert row["counts_towards_totals"] is True


@pytest.mark.contract
@pytest.mark.django_db
def test_removing_a_rule_retires_its_occurrences_instead_of_orphaning_them(keys, workspace, create_user):
    """Deleting is soft and nulls the rule, and both retirement paths select on
    it -- so without this nothing could ever reach these rows again."""
    from rest_framework.test import APIClient

    profile = _profile(workspace, create_user)
    rule = _rule_with_state(workspace, last_success_at=datetime.now(timezone.utc))
    occurrence = _occurrence(workspace, create_user, profile, rule)
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(create_user)
    csrf = client.get("/auth/get-csrf-token/").data["csrf_token"]

    response = client.delete(
        f"/api/workspaces/{workspace.slug}/capacity/google/training-rules/{rule.id}/", HTTP_X_CSRFTOKEN=csrf
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    occurrence.refresh_from_db()
    assert occurrence.state == TrainingEventOccurrence.State.DISAPPEARED
    [row] = _client(create_user).get(URL.format(slug=workspace.slug), OCTOBER).data["trainers"]
    assert row["external_confirmed_sessions"] == 0
