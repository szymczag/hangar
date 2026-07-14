# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import User, Workspace, WorkspaceMember

from plane.ext.runner.constants import RUNNER_CONSENT_VERSION, RunnerAuditAction
from plane.ext.runner.models import RunnerAuditEvent, RunnerInstallation


def installation_url(workspace):
    return f"/api/workspaces/{workspace.slug}/runner/installation/"


def suspend_url(workspace):
    return f"{installation_url(workspace)}suspend/"


def revoke_url(workspace):
    return f"{installation_url(workspace)}revoke/"


def make_workspace_client(workspace, role):
    uid = uuid4().hex[:8]
    user = User.objects.create(
        email=f"runner-{uid}@hangar.test",
        username=f"runner_{uid}",
    )
    WorkspaceMember.objects.create(
        workspace=workspace,
        member=user,
        role=role,
        is_active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def runner_enabled(settings):
    settings.RUNNER_ENABLED = True


@pytest.fixture
def runner_disabled(settings):
    settings.RUNNER_ENABLED = False


@pytest.mark.usefixtures("runner_disabled")
@pytest.mark.contract
class TestRunnerInstanceGate:
    @pytest.mark.django_db
    def test_runner_is_fail_closed_by_default(self, session_client, workspace):
        response = session_client.get(installation_url(workspace))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["code"] == "runner_disabled"

    @pytest.mark.django_db
    def test_disabled_gate_precedes_payload_validation(self, session_client, workspace):
        response = session_client.post(installation_url(workspace), {}, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["code"] == "runner_disabled"
        assert not RunnerInstallation.objects.exists()


@pytest.mark.usefixtures("runner_enabled")
@pytest.mark.contract
class TestRunnerInstallationLifecycle:
    @pytest.mark.django_db
    def test_admin_reads_non_persisted_inactive_state(self, session_client, workspace):
        response = session_client.get(installation_url(workspace))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["state"] == "inactive"
        assert response.data["required_consent_version"] == RUNNER_CONSENT_VERSION
        assert response.data["id"] is None
        assert not RunnerInstallation.objects.exists()

    @pytest.mark.django_db
    @pytest.mark.parametrize("role", [5, 15])
    def test_non_admin_cannot_read_or_activate(self, workspace, role):
        client, _user = make_workspace_client(workspace, role)

        get_response = client.get(installation_url(workspace))
        post_response = client.post(
            installation_url(workspace),
            {"consent_version": RUNNER_CONSENT_VERSION},
            format="json",
        )

        assert get_response.status_code == status.HTTP_403_FORBIDDEN
        assert post_response.status_code == status.HTTP_403_FORBIDDEN
        assert not RunnerInstallation.objects.exists()

    @pytest.mark.django_db
    def test_workspace_membership_does_not_cross_tenant_boundary(self, create_user, session_client, workspace):
        other_workspace = Workspace.objects.create(
            name="Other Workspace",
            slug=f"other-{uuid4().hex[:8]}",
            owner=create_user,
        )

        response = session_client.get(installation_url(other_workspace))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_activation_requires_current_consent(self, session_client, workspace):
        response = session_client.post(
            installation_url(workspace),
            {"consent_version": RUNNER_CONSENT_VERSION + 1},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "runner_consent_required"
        assert not RunnerInstallation.objects.exists()
        assert not RunnerAuditEvent.objects.exists()

    @pytest.mark.django_db
    def test_activation_is_idempotent_and_audited_once(self, session_client, workspace, create_user):
        payload = {"consent_version": RUNNER_CONSENT_VERSION}

        created = session_client.post(installation_url(workspace), payload, format="json")
        repeated = session_client.post(installation_url(workspace), payload, format="json")

        assert created.status_code == status.HTTP_201_CREATED
        assert repeated.status_code == status.HTTP_200_OK
        assert created.data["id"] == repeated.data["id"]
        assert repeated.data["state"] == "active"
        installation = RunnerInstallation.objects.get(workspace=workspace)
        assert installation.activated_by == create_user
        events = RunnerAuditEvent.objects.filter(
            workspace=workspace,
            action=RunnerAuditAction.INSTALLATION_ACTIVATED,
        )
        assert events.count() == 1
        assert events.get().metadata == {
            "previous_state": "inactive",
            "state": "active",
            "consent_version": RUNNER_CONSENT_VERSION,
        }

    @pytest.mark.django_db
    def test_suspend_then_reactivate_records_each_transition(self, session_client, workspace):
        payload = {"consent_version": RUNNER_CONSENT_VERSION}
        session_client.post(installation_url(workspace), payload, format="json")

        suspended = session_client.post(suspend_url(workspace), {}, format="json")
        repeated_suspend = session_client.post(suspend_url(workspace), {}, format="json")
        reactivated = session_client.post(installation_url(workspace), payload, format="json")

        assert suspended.status_code == status.HTTP_200_OK
        assert suspended.data["state"] == "suspended"
        assert repeated_suspend.status_code == status.HTTP_200_OK
        assert reactivated.status_code == status.HTTP_200_OK
        assert reactivated.data["state"] == "active"
        assert RunnerAuditEvent.objects.filter(workspace=workspace).count() == 3

    @pytest.mark.django_db
    def test_revocation_is_terminal(self, session_client, workspace):
        payload = {"consent_version": RUNNER_CONSENT_VERSION}
        session_client.post(installation_url(workspace), payload, format="json")

        revoked = session_client.post(revoke_url(workspace), {}, format="json")
        repeated_revoke = session_client.post(revoke_url(workspace), {}, format="json")
        reactivation = session_client.post(installation_url(workspace), payload, format="json")

        assert revoked.status_code == status.HTTP_200_OK
        assert revoked.data["state"] == "revoked"
        assert repeated_revoke.status_code == status.HTTP_200_OK
        assert reactivation.status_code == status.HTTP_409_CONFLICT
        assert reactivation.data["code"] == "invalid_runner_transition"
        assert RunnerInstallation.objects.get(workspace=workspace).state == "revoked"
        assert RunnerAuditEvent.objects.filter(workspace=workspace).count() == 2

    @pytest.mark.django_db
    def test_suspend_before_activation_is_rejected(self, session_client, workspace):
        response = session_client.post(suspend_url(workspace), {}, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "invalid_runner_transition"


@pytest.mark.usefixtures("runner_enabled")
@pytest.mark.contract
class TestRunnerAuditImmutability:
    @pytest.mark.django_db
    def test_audit_event_cannot_be_updated_or_deleted(self, session_client, workspace):
        session_client.post(
            installation_url(workspace),
            {"consent_version": RUNNER_CONSENT_VERSION},
            format="json",
        )
        event = RunnerAuditEvent.objects.get()

        event.metadata = {"tampered": True}
        with pytest.raises(ValidationError, match="immutable"):
            event.save()
        with pytest.raises(ValidationError, match="immutable"):
            event.delete()
        with pytest.raises(ValidationError, match="immutable"):
            RunnerAuditEvent.objects.filter(pk=event.pk).update(metadata={"tampered": True})
        with pytest.raises(ValidationError, match="immutable"):
            RunnerAuditEvent.objects.filter(pk=event.pk).delete()
