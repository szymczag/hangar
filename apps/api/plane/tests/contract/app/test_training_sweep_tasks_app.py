# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet

from plane.ext.capacity.crypto import encrypt_value
from plane.ext.capacity.training_sync import (
    claim_sweeps,
    ensure_sync_states,
    prune_retired_occurrences,
    release_sweep,
)
from plane.ext.models import (
    GoogleTrainingRule,
    TrainerProfile,
    TrainingCalendarSyncState,
    TrainingEventOccurrence,
)
from plane.ext.tasks import dispatch_training_calendar_sweeps, prune_training_event_occurrences

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def keys(settings):
    settings.CALENDAR_TOKEN_ENCRYPTION_KEYS = (Fernet.generate_key().decode(),)
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    settings.GOOGLE_TRAINING_MATERIALIZATION_ENABLED = True
    return settings


def _rule(workspace, label="Shared training calendar"):
    encrypted, key_id = encrypt_value("shared@example.test")
    return GoogleTrainingRule.objects.create(
        workspace=workspace,
        label=label,
        encrypted_calendar_id=encrypted,
        encrypted_organizer=encrypt_value("organizer@example.test")[0],
        encryption_key_id=key_id,
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_every_configured_rule_gains_a_row_it_can_be_claimed_through(keys, workspace):
    _rule(workspace, label="One")
    _rule(workspace, label="Two")

    assert ensure_sync_states(NOW) == 2
    assert TrainingCalendarSyncState.objects.count() == 2
    # Idempotent: a second pass adds nothing.
    assert ensure_sync_states(NOW) == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_claiming_a_calendar_takes_it_out_of_circulation(keys, workspace):
    _rule(workspace)
    ensure_sync_states(NOW)

    first = claim_sweeps(NOW)
    second = claim_sweeps(NOW)

    assert len(first) == 1
    assert second == [], "a leased calendar must not be handed to a second worker"


@pytest.mark.contract
@pytest.mark.django_db
def test_an_expired_lease_is_reclaimable(keys, workspace):
    """What makes a worker dying mid-sweep self-healing."""
    _rule(workspace)
    ensure_sync_states(NOW)
    claim_sweeps(NOW, lease_seconds=60)

    assert len(claim_sweeps(NOW + timedelta(minutes=2))) == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_releasing_requires_still_holding_the_lease(keys, workspace):
    """A worker that overran must not clear somebody else's claim."""
    _rule(workspace)
    ensure_sync_states(NOW)
    [(rule_id, token, _full)] = claim_sweeps(NOW)

    assert release_sweep(rule_id, "00000000-0000-0000-0000-000000000000") == 0
    assert release_sweep(rule_id, token) == 1
    assert len(claim_sweeps(NOW)) == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_a_calendar_backing_off_is_not_claimed_before_its_time(keys, workspace):
    _rule(workspace)
    ensure_sync_states(NOW)
    TrainingCalendarSyncState.objects.update(available_at=NOW + timedelta(hours=1))

    assert claim_sweeps(NOW) == []
    assert len(claim_sweeps(NOW + timedelta(hours=1))) == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_the_first_pass_on_a_calendar_is_a_full_one(keys, workspace):
    _rule(workspace)
    ensure_sync_states(NOW)

    [(_rule_id, _token, full)] = claim_sweeps(NOW)

    assert full is True


@pytest.mark.contract
@pytest.mark.django_db
def test_the_dispatcher_does_nothing_while_materialization_is_off(keys, workspace, monkeypatch):
    keys.GOOGLE_TRAINING_MATERIALIZATION_ENABLED = False
    _rule(workspace)

    assert dispatch_training_calendar_sweeps() == 0
    assert TrainingCalendarSyncState.objects.count() == 0


@pytest.mark.contract
@pytest.mark.django_db
def test_the_dispatcher_claims_and_hands_off_each_due_calendar(keys, workspace, monkeypatch):
    _rule(workspace)
    sent = []
    monkeypatch.setattr(
        "plane.ext.tasks.sweep_training_calendar.apply_async", lambda args=None, **kwargs: sent.append(args)
    )

    assert dispatch_training_calendar_sweeps() == 1
    assert len(sent) == 1
    assert claim_sweeps(datetime.now(timezone.utc)) == [], "the dispatched calendar stays leased"


@pytest.mark.contract
@pytest.mark.django_db
def test_pruning_removes_only_what_the_sweep_retired(keys, workspace, create_user):
    """Past training is the reporting product; it is never pruned."""
    profile = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    rule = _rule(workspace)
    long_ago = NOW - timedelta(days=200)
    common = {
        "workspace": workspace,
        "trainer": create_user,
        "trainer_profile": profile,
        "rule": rule,
        "calendar_id_hash": "hash",
        "starts_at": long_ago,
        "ends_at": long_ago + timedelta(hours=4),
        "status": TrainingEventOccurrence.Status.CONFIRMED,
        "first_seen_at": long_ago,
        "last_seen_at": long_ago,
    }
    TrainingEventOccurrence.objects.create(event_key="kept", state=TrainingEventOccurrence.State.ACTIVE, **common)
    TrainingEventOccurrence.objects.create(
        event_key="retired", state=TrainingEventOccurrence.State.DISAPPEARED, **common
    )

    assert prune_retired_occurrences(NOW) == 1
    assert list(TrainingEventOccurrence.objects.values_list("event_key", flat=True)) == ["kept"]


@pytest.mark.contract
@pytest.mark.django_db
def test_a_recently_retired_occurrence_is_kept_for_its_grace_period(keys, workspace, create_user):
    profile = TrainerProfile.objects.create(workspace=workspace, user=create_user)
    rule = _rule(workspace)
    TrainingEventOccurrence.objects.create(
        workspace=workspace,
        trainer=create_user,
        trainer_profile=profile,
        rule=rule,
        event_key="recent",
        calendar_id_hash="hash",
        starts_at=NOW,
        ends_at=NOW + timedelta(hours=2),
        status=TrainingEventOccurrence.Status.CONFIRMED,
        state=TrainingEventOccurrence.State.CANCELLED,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )

    assert prune_training_event_occurrences() == 0
    assert TrainingEventOccurrence.objects.count() == 1
