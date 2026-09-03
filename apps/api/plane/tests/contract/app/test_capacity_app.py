# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from plane.ext.models import CapacityAuditEvent, TrainerProfile


@pytest.mark.contract
@pytest.mark.django_db
def test_trainer_opt_in_requires_and_accepts_server_issued_csrf(settings, workspace, create_user):
    settings.GOOGLE_CALENDAR_CAPACITY_ENABLED = True
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(create_user)
    url = f"/api/workspaces/{workspace.slug}/capacity/trainers/me/"

    rejected = client.post(url)

    assert rejected.status_code == status.HTTP_403_FORBIDDEN
    assert not TrainerProfile.objects.filter(workspace=workspace, user=create_user).exists()
    assert not CapacityAuditEvent.objects.filter(
        workspace_id=workspace.id,
        actor_id=create_user.id,
        action=CapacityAuditEvent.Action.TRAINER_ACTIVATED,
    ).exists()

    csrf_response = client.get("/auth/get-csrf-token/")
    accepted = client.post(url, HTTP_X_CSRFTOKEN=csrf_response.data["csrf_token"])

    assert accepted.status_code == status.HTTP_201_CREATED
    assert accepted.data["user_id"] == str(create_user.id)
    assert accepted.data["status"] == TrainerProfile.Status.ACTIVE
    assert TrainerProfile.objects.filter(
        workspace=workspace,
        user=create_user,
        status=TrainerProfile.Status.ACTIVE,
    ).exists()
    assert CapacityAuditEvent.objects.filter(
        workspace_id=workspace.id,
        actor_id=create_user.id,
        action=CapacityAuditEvent.Action.TRAINER_ACTIVATED,
    ).exists()
