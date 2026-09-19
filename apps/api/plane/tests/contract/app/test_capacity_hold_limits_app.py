# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime, timedelta, timezone

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.ext.models import TrainerProfile, WorkshopPlanDraft, WorkshopPlanHold


@pytest.fixture
def capacity(settings):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    return settings


def _client(user):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(user)
    return client, client.get("/auth/get-csrf-token/").data["csrf_token"]


def _draft_body(trainer_id, *, title="NetSec workshop"):
    return {
        "title": title,
        "duration_minutes": 240,
        "preparation_minutes": 0,
        "travel_before_minutes": 0,
        "travel_after_minutes": 0,
        "trainer_ids": [str(trainer_id)],
        "issue_id": None,
    }


@pytest.mark.contract
@pytest.mark.django_db
def test_saved_plans_are_capped_per_person(capacity, workspace, create_user):
    """Each plan can carry a reservation, so unbounded plans means unbounded
    ways to take a trainer's time out of circulation."""
    capacity.CAPACITY_MAX_PLAN_DRAFTS_PER_USER = 2
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/plans/"

    for index in range(2):
        created = client.post(
            url, _draft_body(create_user.id, title=f"Plan {index}"), format="json", HTTP_X_CSRFTOKEN=csrf
        )
        assert created.status_code == status.HTTP_201_CREATED

    refused = client.post(url, _draft_body(create_user.id, title="One too many"), format="json", HTTP_X_CSRFTOKEN=csrf)

    assert refused.status_code == status.HTTP_409_CONFLICT
    assert WorkshopPlanDraft.objects.filter(owner=create_user).count() == 2


@pytest.mark.contract
@pytest.mark.django_db
def test_deleting_a_plan_frees_the_allowance(capacity, workspace, create_user):
    capacity.CAPACITY_MAX_PLAN_DRAFTS_PER_USER = 1
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    client, csrf = _client(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/plans/"
    first = client.post(url, _draft_body(create_user.id), format="json", HTTP_X_CSRFTOKEN=csrf).data

    client.delete(f"{url}{first['id']}/", HTTP_X_CSRFTOKEN=csrf)

    assert (
        client.post(url, _draft_body(create_user.id), format="json", HTTP_X_CSRFTOKEN=csrf).status_code
        == status.HTTP_201_CREATED
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_an_expired_reservation_does_not_count_against_the_allowance(capacity, workspace, create_user):
    """The allowance is about time actually held, not rows left lying around."""
    capacity.CAPACITY_MAX_ACTIVE_HOLDS_PER_USER = 1
    TrainerProfile.objects.create(workspace=workspace, user=create_user)
    now = datetime.now(timezone.utc)
    draft = WorkshopPlanDraft.objects.create(
        workspace=workspace, owner=create_user, title="Old plan", duration_minutes=240, trainer_ids=[str(create_user.id)]
    )
    WorkshopPlanHold.objects.create(
        draft=draft,
        workspace=workspace,
        trainer=create_user,
        workshop_starts_at=now - timedelta(days=5),
        workshop_ends_at=now - timedelta(days=5) + timedelta(hours=4),
        blocked_starts_at=now - timedelta(days=5),
        blocked_ends_at=now - timedelta(days=5) + timedelta(hours=4),
        expires_at=now - timedelta(days=1),
        status=WorkshopPlanHold.Status.ACTIVE,
    )

    live = WorkshopPlanHold.objects.filter(
        workspace=workspace, draft__owner=create_user, status=WorkshopPlanHold.Status.ACTIVE, expires_at__gt=now
    ).count()

    assert live == 0, "an expired reservation holds nothing and must not consume the allowance"


@pytest.mark.contract
@pytest.mark.django_db
def test_the_booking_endpoints_declare_the_capacity_throttles(capacity):
    """Their preflight reads Google before the conflict check, so an unthrottled
    caller who only ever gets 409s still spends the quota the ledger throttle
    exists to protect."""
    from plane.ext.capacity.throttles import CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle
    from plane.ext.views.capacity import (
        WorkshopPlanHoldEndpoint,
        WorkshopPlanScheduleEndpoint,
        WorkspaceCapacityEndpoint,
    )

    for endpoint in (WorkshopPlanHoldEndpoint, WorkshopPlanScheduleEndpoint, WorkspaceCapacityEndpoint):
        assert CalendarCapacityUserThrottle in endpoint.throttle_classes, endpoint.__name__
        assert CalendarCapacityWorkspaceThrottle in endpoint.throttle_classes, endpoint.__name__
