# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Writing a scheduled workshop into the shared training calendar.

Every test here is about a way the loop could produce two invitations, none at
all, or one nobody can recognize -- the three failures that would make a
coordinator go back to entering trainings by hand.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet

from plane.db.models import Issue, IssueType, Project
from plane.ext.capacity.calendar_sync import (
    claim_rows,
    event_id_for,
    mark_sessions_absent,
    reconcile_orphans,
    reconcile_session,
    sync_row,
)
from plane.ext.capacity.google import GoogleCalendarError
from plane.ext.models import (
    GoogleCalendarCredential,
    GoogleTrainingRule,
    TrainerCalendarSelection,
    TrainerProfile,
    WorkshopSchedule,
    WorkshopSession,
    WorkshopSessionCalendarEvent,
)
from plane.ext.capacity.crypto import encrypt_value

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)
STARTS = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def writeback(settings):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.GOOGLE_CALENDAR_WRITEBACK_ENABLED = True
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    return settings


def _credential(user, subject, email, *, scopes=("https://www.googleapis.com/auth/calendar.events",)):
    encrypted, key_id = encrypt_value(email)
    return GoogleCalendarCredential.objects.create(
        user=user,
        google_subject=subject,
        encrypted_refresh_token=encrypted,
        encrypted_google_email=encrypted,
        encryption_key_id=key_id,
        granted_scopes=list(scopes),
    )


def _rule(workspace, writer=None):
    encrypted, key_id = encrypt_value("shared@example.test")
    return GoogleTrainingRule.objects.create(
        workspace=workspace,
        label="Shared training calendar",
        encrypted_calendar_id=encrypted,
        encryption_key_id=key_id,
        writer_credential=writer,
    )


def _session(workspace, user, *, trainers):
    project = Project.objects.create(
        name="Training", identifier="WB", workspace=workspace, created_by=user
    )
    issue_type = IssueType.objects.create(name="Workshop", workspace=workspace)
    issue = Issue.objects.create(
        name="Network security", project=project, workspace=workspace, created_by=user, type=issue_type
    )
    schedule = WorkshopSchedule.objects.create(
        workspace=workspace,
        project=project,
        issue=issue,
        starts_at=STARTS,
        ends_at=STARTS + timedelta(hours=4),
    )
    session = WorkshopSession.objects.create(
        schedule=schedule, starts_at=STARTS, ends_at=STARTS + timedelta(hours=4)
    )
    session.trainers.set(trainers)
    return session


def _connected_trainer(workspace, user, email="trainer@example.test"):
    profile = TrainerProfile.objects.create(workspace=workspace, user=user)
    credential = _credential(user, f"trainer-{user.id}", email)
    TrainerCalendarSelection.objects.create(trainer=profile, credential=credential)
    return profile


@pytest.mark.contract
@pytest.mark.django_db
def test_scheduling_records_the_intent_without_calling_google(writeback, workspace, create_user):
    """Planning must not wait for a calendar API, or nobody will use the planner."""
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])

    touched = reconcile_session(session, actor=create_user)

    assert len(touched) == 1
    row = WorkshopSessionCalendarEvent.objects.get()
    assert row.state == WorkshopSessionCalendarEvent.State.PENDING
    assert row.google_event_id == event_id_for(session.id, create_user.id)
    assert row.synced_revision != row.revision


@pytest.mark.contract
@pytest.mark.django_db
def test_a_rule_with_no_writer_still_lets_the_session_be_planned(writeback, workspace, create_user):
    _connected_trainer(workspace, create_user)
    _rule(workspace, None)
    session = _session(workspace, create_user, trainers=[create_user])

    reconcile_session(session, actor=create_user)

    assert WorkshopSessionCalendarEvent.objects.get().state == (
        WorkshopSessionCalendarEvent.State.BLOCKED_NO_WRITER
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_an_already_existing_event_is_updated_rather_than_duplicated(writeback, workspace, create_user):
    """The property the derived identifier exists for.

    A redelivered message, or a retry after an answer that never arrived, must
    reconcile the event it already created instead of creating a second one.
    """
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()

    client = MagicMock()
    client.insert_event.side_effect = GoogleCalendarError("already_exists")
    client.update_event.return_value = {"iCalUID": "written@example.test"}

    assert sync_row(client, row, now=NOW)["result"] == "synced"
    assert client.update_event.call_count == 1
    row.refresh_from_db()
    assert row.state == WorkshopSessionCalendarEvent.State.SYNCED
    assert row.synced_revision == row.revision


@pytest.mark.contract
@pytest.mark.django_db
def test_the_invitation_goes_to_the_address_recognition_will_match(writeback, workspace, create_user):
    """A different address would send an invitation nothing ever recognizes."""
    _connected_trainer(workspace, create_user, email="verified@example.test")
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()

    client = MagicMock()
    client.insert_event.return_value = {"iCalUID": "written@example.test"}
    sync_row(client, row, now=NOW)

    payload = client.insert_event.call_args.args[2]
    assert payload["attendees"] == [{"email": "verified@example.test"}]
    assert payload["extendedProperties"]["private"]["hangarSession"] == str(session.id)


@pytest.mark.contract
@pytest.mark.django_db
def test_the_event_covers_the_delivery_and_not_the_buffers(writeback, workspace, create_user):
    """A three-hour entry for a one-hour training surprises people reading it."""
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    session.preparation_minutes = 120
    session.travel_after_minutes = 90
    session.save()
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()

    client = MagicMock()
    client.insert_event.return_value = {}
    sync_row(client, row, now=NOW)

    payload = client.insert_event.call_args.args[2]
    assert payload["start"]["dateTime"] == "2026-11-03T09:00:00Z"
    assert payload["end"]["dateTime"] == "2026-11-03T13:00:00Z"


@pytest.mark.contract
@pytest.mark.django_db
def test_a_removed_trainer_has_their_invitation_withdrawn(writeback, workspace, create_user):
    from plane.db.models import User

    other = User.objects.create(
        email="other@example.test", username="other-trainer", first_name="Other", last_name="Trainer"
    )
    _connected_trainer(workspace, create_user)
    _connected_trainer(workspace, other, email="other-verified@example.test")
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user, other])
    reconcile_session(session, actor=create_user)
    for row in WorkshopSessionCalendarEvent.objects.all():
        row.synced_revision = row.revision
        row.state = WorkshopSessionCalendarEvent.State.SYNCED
        row.save()

    session.trainers.set([create_user])
    reconcile_session(session, actor=create_user)

    withdrawn = WorkshopSessionCalendarEvent.objects.get(trainer=other)
    assert withdrawn.intent == WorkshopSessionCalendarEvent.Intent.ABSENT
    assert withdrawn.state == WorkshopSessionCalendarEvent.State.PENDING


@pytest.mark.contract
@pytest.mark.django_db
def test_a_row_that_never_reached_google_needs_no_withdrawal(writeback, workspace, create_user):
    """There is no event to remove, so the row is finished rather than queued."""
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)

    mark_sessions_absent([session.id], actor=create_user)

    row = WorkshopSessionCalendarEvent.objects.get()
    assert row.intent == WorkshopSessionCalendarEvent.Intent.ABSENT
    assert row.state == WorkshopSessionCalendarEvent.State.SYNCED


@pytest.mark.contract
@pytest.mark.django_db
def test_the_row_outlives_the_session_it_has_to_withdraw(writeback, workspace, create_user):
    """The row matters most exactly when the session is gone."""
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()
    row.synced_revision = row.revision
    row.save()
    session_id = session.id

    mark_sessions_absent([session_id], actor=create_user)
    session.delete(soft=False)

    surviving = WorkshopSessionCalendarEvent.objects.get(source_session_id=session_id)
    assert surviving.intent == WorkshopSessionCalendarEvent.Intent.ABSENT
    assert surviving.google_event_id


@pytest.mark.contract
@pytest.mark.django_db
def test_a_writer_swapped_under_a_queued_row_blocks_it(writeback, workspace, create_user):
    """Consent was given for one account to act, not for whoever holds it later."""
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()
    writer.google_subject = "somebody-else"
    writer.save(update_fields=["google_subject"])
    row.refresh_from_db()

    client = MagicMock()
    assert sync_row(client, row, now=NOW)["result"] == "blocked"
    assert client.insert_event.call_count == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_a_rate_limit_backs_off_instead_of_failing_the_row(writeback, workspace, create_user):
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()

    client = MagicMock()
    client.insert_event.side_effect = GoogleCalendarError("rate_limited")

    assert sync_row(client, row, now=NOW)["result"] == "error"
    row.refresh_from_db()
    assert row.state == WorkshopSessionCalendarEvent.State.PENDING
    assert row.attempts == 1
    assert row.available_at > NOW


@pytest.mark.contract
@pytest.mark.django_db
def test_only_rows_that_owe_work_are_claimed(writeback, workspace, create_user):
    """The predicate is the revision, not the state.

    A row stuck in `failed` becomes claimable again the moment somebody edits
    the session, without anybody having to reason about how it got stuck.
    """
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()

    assert len(claim_rows(NOW)) == 1

    row.refresh_from_db()
    row.synced_revision = row.revision
    row.lease_token = None
    row.lease_expires_at = None
    row.save()

    assert claim_rows(NOW) == []


@pytest.mark.contract
@pytest.mark.django_db
def test_nothing_is_recorded_while_write_back_is_off(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.GOOGLE_CALENDAR_WRITEBACK_ENABLED = False
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    _connected_trainer(workspace, create_user)
    session = _session(workspace, create_user, trainers=[create_user])

    assert reconcile_session(session, actor=create_user) == []
    assert WorkshopSessionCalendarEvent.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_removing_the_schedule_withdraws_before_the_sessions_go(writeback, workspace, create_user):
    """The order matters: afterwards there is nothing left to enumerate.

    Deleting the schedule hard-deletes its sessions, so the invitations have to
    be named while the sessions still exist or they are never withdrawn.
    """
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()
    row.synced_revision = row.revision
    row.state = WorkshopSessionCalendarEvent.State.SYNCED
    row.save()

    departing = [session.id]
    mark_sessions_absent(departing, actor=create_user)
    session.schedule.delete(soft=False)

    surviving = WorkshopSessionCalendarEvent.objects.get(source_session_id=departing[0])
    assert surviving.intent == WorkshopSessionCalendarEvent.Intent.ABSENT
    assert surviving.state == WorkshopSessionCalendarEvent.State.PENDING


@pytest.mark.contract
@pytest.mark.django_db
def test_a_session_deleted_behind_the_views_is_caught_by_the_reconciler(writeback, workspace, create_user):
    """Deleting the work item cascades past every helper in the views.

    The reconciler, not those helpers, is what guarantees the calendar ends up
    right -- they only make the ordinary case prompt.
    """
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()
    row.synced_revision = row.revision
    row.state = WorkshopSessionCalendarEvent.State.SYNCED
    row.save()

    # Straight past the endpoints, the way an issue deletion arrives.
    session.schedule.issue.delete(soft=False)

    assert reconcile_orphans(now=NOW)

    row.refresh_from_db()
    assert row.intent == WorkshopSessionCalendarEvent.Intent.ABSENT
    assert row.state == WorkshopSessionCalendarEvent.State.PENDING


@pytest.mark.contract
@pytest.mark.django_db
def test_the_reconciler_leaves_live_sessions_alone(writeback, workspace, create_user):
    """It runs every ten minutes, so a false positive would be expensive."""
    _connected_trainer(workspace, create_user)
    writer = _credential(create_user, "writer-subject", "coordinator@example.test")
    _rule(workspace, writer)
    session = _session(workspace, create_user, trainers=[create_user])
    reconcile_session(session, actor=create_user)
    row = WorkshopSessionCalendarEvent.objects.get()
    row.synced_revision = row.revision
    row.state = WorkshopSessionCalendarEvent.State.SYNCED
    row.save()

    assert reconcile_orphans(now=NOW) == []

    row.refresh_from_db()
    assert row.intent == WorkshopSessionCalendarEvent.Intent.PRESENT
    assert row.state == WorkshopSessionCalendarEvent.State.SYNCED
