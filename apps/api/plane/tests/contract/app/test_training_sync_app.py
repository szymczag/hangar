# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from plane.ext.capacity.crypto import decrypt_value, encrypt_value
from plane.ext.capacity.google import GoogleCalendarError
from plane.ext.capacity.training_events import EVENTS_SCOPE
from plane.ext.capacity.training_sync import sweep_rule
from plane.ext.models import (
    GoogleCalendarCredential,
    GoogleTrainingRule,
    TrainerCalendarSelection,
    TrainerProfile,
    TrainerTrainingSyncState,
    TrainingCalendarSyncState,
    TrainingEventOccurrence,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
STARTS = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
ORGANIZER = "organizer@example.test"
TRAINER_EMAIL = "trainer@example.test"
CALENDAR = "shared@example.test"


class FakeClient:
    """Stands in for the Google client; records what the sweep asked for."""

    def __init__(self, events, *, fail=None):
        self.events = events
        self.fail = fail
        self.calls = []

    def list_training_events(self, credential, calendar_id, *, time_min, time_max, updated_min=None):
        self.calls.append({"calendar_id": calendar_id, "updated_min": updated_min, "time_min": time_min})
        if self.fail:
            raise GoogleCalendarError(self.fail)
        return [
            event
            for event in self.events
            if time_min <= event["start"]["dateTime"] < time_max
        ]


def _event(*, key_id="one", starts=STARTS, hours=4, response="accepted", status=None, summary=None):
    event = {
        "id": key_id,
        "iCalUID": f"{key_id}@example.test",
        "organizer": {"email": ORGANIZER},
        "attendees": [{"email": TRAINER_EMAIL, "responseStatus": response}],
        "start": {"dateTime": starts.isoformat().replace("+00:00", "Z")},
        "end": {"dateTime": (starts + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")},
        "calendar_timezone": "UTC",
    }
    if status:
        event["status"] = status
    if summary is not None:
        event["summary"] = summary
    return event


def _consenting_trainer(workspace, user, settings, *, email=TRAINER_EMAIL, consented=True):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = getattr(
        settings, "CALENDAR_TOKEN_ENCRYPTION_KEYS", None
    ) or (Fernet.generate_key().decode(),)
    trainer = TrainerProfile.objects.create(workspace=workspace, user=user)
    encrypted_email, key_id = encrypt_value(email)
    credential = GoogleCalendarCredential.objects.create(
        user=user,
        google_subject=f"subject-{user.id}",
        encrypted_refresh_token=encrypted_email,
        encrypted_google_email=encrypted_email,
        encryption_key_id=key_id,
        granted_scopes=[EVENTS_SCOPE] if consented else [],
    )
    TrainerCalendarSelection.objects.create(
        trainer=trainer, credential=credential, training_events_enabled=consented
    )
    return trainer


def _rule(workspace):
    encrypted_calendar, key_id = encrypt_value(CALENDAR)
    return GoogleTrainingRule.objects.create(
        workspace=workspace,
        label="Shared training calendar",
        encrypted_calendar_id=encrypted_calendar,
        encrypted_organizer=encrypt_value(ORGANIZER)[0],
        encryption_key_id=key_id,
    )


@pytest.fixture
def keys(settings):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    return settings


@pytest.mark.contract
@pytest.mark.django_db
def test_a_recognized_invitation_becomes_an_occurrence_with_its_title(keys, workspace, create_user):
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    client = FakeClient([_event(summary="Network security — Acme")])

    result = sweep_rule(client, rule, now=NOW, full=True)

    assert result["matched"] == 1
    occurrence = TrainingEventOccurrence.objects.get()
    assert occurrence.starts_at == STARTS
    assert occurrence.status == TrainingEventOccurrence.Status.CONFIRMED
    assert occurrence.state == TrainingEventOccurrence.State.ACTIVE
    assert occurrence.rule_label == "Shared training calendar"
    assert decrypt_value(occurrence.encrypted_summary, occurrence.encryption_key_id) == "Network security — Acme"


@pytest.mark.contract
@pytest.mark.django_db
def test_an_event_that_matches_no_rule_leaves_no_trace_of_its_title(keys, workspace, create_user):
    """The security boundary of the titles feature, asserted end to end."""
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    stranger = _event(key_id="other", summary="Somebody's private appointment")
    stranger["organizer"] = {"email": "someone-else@example.test"}
    client = FakeClient([stranger])

    result = sweep_rule(client, rule, now=NOW, full=True)

    assert result["matched"] == 0
    assert TrainingEventOccurrence.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_an_unanswered_invitation_is_pending_rather_than_confirmed(keys, workspace, create_user):
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)

    sweep_rule(FakeClient([_event(response="needsAction")]), rule, now=NOW, full=True)

    assert TrainingEventOccurrence.objects.get().status == TrainingEventOccurrence.Status.PENDING


@pytest.mark.contract
@pytest.mark.django_db
def test_sweeping_twice_updates_the_same_row(keys, workspace, create_user):
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    sweep_rule(FakeClient([_event(response="needsAction")]), rule, now=NOW, full=True)

    sweep_rule(FakeClient([_event(response="accepted")]), rule, now=NOW + timedelta(hours=1), full=True)

    occurrence = TrainingEventOccurrence.objects.get()
    assert occurrence.status == TrainingEventOccurrence.Status.CONFIRMED
    assert occurrence.first_seen_at == NOW


@pytest.mark.contract
@pytest.mark.django_db
def test_a_cancelled_invitation_is_retired_without_waiting_for_a_full_scan(keys, workspace, create_user):
    """A cancelled training that goes on inflating a report is what this prevents."""
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    sweep_rule(FakeClient([_event()]), rule, now=NOW, full=True)

    cancelled = _event(status="cancelled")
    cancelled.pop("attendees")
    sweep_rule(FakeClient([cancelled]), rule, now=NOW + timedelta(minutes=15))

    assert TrainingEventOccurrence.objects.get().state == TrainingEventOccurrence.State.CANCELLED


@pytest.mark.contract
@pytest.mark.django_db
def test_an_incremental_pass_never_concludes_that_anything_disappeared(keys, workspace, create_user):
    """Otherwise the first quiet run empties the table.

    An incremental read returns only what Google says changed, so an empty
    answer means "nothing changed", not "everything is gone".
    """
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    sweep_rule(FakeClient([_event()]), rule, now=NOW, full=True)

    sweep_rule(FakeClient([]), rule, now=NOW + timedelta(minutes=15))

    assert TrainingEventOccurrence.objects.get().state == TrainingEventOccurrence.State.ACTIVE


@pytest.mark.contract
@pytest.mark.django_db
def test_a_full_pass_retires_what_it_no_longer_sees(keys, workspace, create_user):
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    sweep_rule(FakeClient([_event()]), rule, now=NOW, full=True)

    sweep_rule(FakeClient([]), rule, now=NOW + timedelta(days=1), full=True)

    assert TrainingEventOccurrence.objects.get().state == TrainingEventOccurrence.State.DISAPPEARED


@pytest.mark.contract
@pytest.mark.django_db
def test_an_incremental_pass_asks_google_only_for_what_changed(keys, workspace, create_user):
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    sweep_rule(FakeClient([_event()]), rule, now=NOW, full=True)

    client = FakeClient([])
    sweep_rule(client, rule, now=NOW + timedelta(minutes=15))

    assert all(call["updated_min"] is not None for call in client.calls)


@pytest.mark.contract
@pytest.mark.django_db
def test_a_trainer_who_never_consented_is_recorded_as_such_and_gets_no_rows(keys, workspace, create_user):
    """A report must be able to tell this from a trainer who ran no training."""
    trainer = _consenting_trainer(workspace, create_user, keys, consented=False)
    rule = _rule(workspace)

    result = sweep_rule(FakeClient([_event()]), rule, now=NOW, full=True)

    assert result["readers"] == 0
    assert TrainingEventOccurrence.objects.count() == 0
    state = TrainerTrainingSyncState.objects.get(trainer_profile=trainer)
    assert state.consent_state == TrainerTrainingSyncState.ConsentState.CONSENT_MISSING


@pytest.mark.contract
@pytest.mark.django_db
def test_a_google_failure_backs_off_instead_of_losing_what_was_already_known(keys, workspace, create_user):
    _consenting_trainer(workspace, create_user, keys)
    rule = _rule(workspace)
    sweep_rule(FakeClient([_event()]), rule, now=NOW, full=True)

    result = sweep_rule(FakeClient([], fail="rate_limited"), rule, now=NOW + timedelta(minutes=15))

    assert result["error"] == "rate_limited"
    assert TrainingEventOccurrence.objects.get().state == TrainingEventOccurrence.State.ACTIVE
    state = TrainingCalendarSyncState.objects.get(rule=rule)
    assert state.failure_count == 1
    assert state.available_at > NOW + timedelta(minutes=15)
