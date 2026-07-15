# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import User, Workspace, WorkspaceMember

from plane.ext.runner.consent import (
    CURRENT_RUNNER_CONSENT,
    RUNNER_CONSENT_CONTRACTS,
    RUNNER_CONSENT_TEXT,
    RUNNER_CONSENT_V1_DIGEST,
    consent_digest,
)
from plane.ext.runner.models import (
    RunnerAuditAction,
    RunnerAuditEvent,
    RunnerInstallation,
    RunnerInstallationState,
)
from plane.ext.runner.services import (
    RunnerAuditContext,
    RunnerConsentError,
    RunnerInstallationService,
    RunnerPermissionError,
    RunnerServiceError,
    RunnerTransitionError,
)
from plane.ext.runner.throttles import RunnerMutationThrottle, RunnerUserMutationThrottle
from plane.ext.runner.views import runner_error_response


def installation_url(workspace):
    return f"/api/workspaces/{workspace.slug}/runner/installation/"


def suspend_url(workspace):
    return f"{installation_url(workspace)}suspend/"


def revoke_url(workspace):
    return f"{installation_url(workspace)}revoke/"


def activation_payload():
    return {
        "consent_version": CURRENT_RUNNER_CONSENT.version,
        "consent_digest": CURRENT_RUNNER_CONSENT.digest,
    }


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


@pytest.mark.contract
class TestRunnerConsentContract:
    def test_consent_digest_is_bound_to_canonical_text(self):
        assert RUNNER_CONSENT_V1_DIGEST == "6713ce3d0b6f6e37853b7d4892484264c790a9bda76decf76fc3a1dc3aaa9fcf"
        assert CURRENT_RUNNER_CONSENT.digest == consent_digest(RUNNER_CONSENT_TEXT)
        assert len(CURRENT_RUNNER_CONSENT.digest) == 64
        assert CURRENT_RUNNER_CONSENT.document_id.endswith(f"v{CURRENT_RUNNER_CONSENT.version}")

    def test_published_consent_contracts_are_retained_in_an_immutable_registry(self):
        assert RUNNER_CONSENT_CONTRACTS[1] is CURRENT_RUNNER_CONSENT
        with pytest.raises(TypeError):
            RUNNER_CONSENT_CONTRACTS[2] = CURRENT_RUNNER_CONSENT


@pytest.mark.contract
class TestRunnerAuditContext:
    @pytest.mark.parametrize(
        "values",
        [
            {"request_id": ""},
            {"request_id": "valid", "source_ip": "not-an-ip"},
            {"request_id": "valid", "user_agent": "invalid\nagent"},
        ],
    )
    def test_rejects_unbounded_or_ambiguous_evidence(self, values):
        with pytest.raises(ValueError):
            RunnerAuditContext(**values)


@pytest.mark.contract
class TestRunnerErrorResponse:
    @pytest.mark.parametrize(
        ("error", "expected_message"),
        [
            (RunnerConsentError("sensitive-consent-digest"), "The current Runner consent must be accepted."),
            (RunnerServiceError("sensitive-stack-trace-detail"), "Runner request could not be completed."),
        ],
    )
    def test_does_not_expose_service_error_details(self, error, expected_message):
        response = runner_error_response(error)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error": expected_message,
            "code": error.code,
        }
        assert str(error) not in response.data["error"]


@pytest.mark.usefixtures("runner_disabled")
@pytest.mark.contract
class TestRunnerInstanceGate:
    @pytest.mark.django_db
    def test_runner_is_fail_closed_when_disabled(self, session_client, workspace):
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
class TestRunnerInstallationAuthorization:
    @pytest.mark.django_db
    @pytest.mark.parametrize("role", [5, 15])
    def test_non_admin_cannot_read_or_mutate(self, workspace, role):
        client, _user = make_workspace_client(workspace, role)

        responses = [
            client.get(installation_url(workspace)),
            client.post(installation_url(workspace), activation_payload(), format="json"),
            client.post(suspend_url(workspace), {}, format="json"),
            client.post(revoke_url(workspace), {}, format="json"),
        ]

        assert {response.status_code for response in responses} == {status.HTTP_404_NOT_FOUND}
        assert {response.data["code"] for response in responses} == {"runner_not_found"}
        assert not RunnerInstallation.objects.exists()

    @pytest.mark.django_db
    def test_workspace_membership_does_not_cross_tenant_boundary(self, create_user, session_client, workspace):
        other_workspace = Workspace.objects.create(
            name="Other Workspace",
            slug=f"other-{uuid4().hex[:8]}",
            owner=create_user,
        )

        responses = [
            session_client.get(installation_url(other_workspace)),
            session_client.post(installation_url(other_workspace), activation_payload(), format="json"),
            session_client.post(suspend_url(other_workspace), {}, format="json"),
            session_client.post(revoke_url(other_workspace), {}, format="json"),
        ]

        assert {response.status_code for response in responses} == {status.HTTP_404_NOT_FOUND}
        assert {response.data["code"] for response in responses} == {"runner_not_found"}
        assert not RunnerInstallation.objects.filter(workspace=other_workspace).exists()

    @pytest.mark.django_db
    def test_service_rejects_direct_non_admin_call(self, workspace):
        _client, member = make_workspace_client(workspace, role=15)

        with pytest.raises(RunnerPermissionError, match="Admin"):
            RunnerInstallationService.activate(
                workspace=workspace,
                actor=member,
                **activation_payload(),
            )

        assert not RunnerInstallation.objects.exists()
        assert not RunnerAuditEvent.objects.exists()

    @pytest.mark.django_db
    def test_non_admin_is_rejected_before_activation_payload_validation(self, workspace):
        client, _member = make_workspace_client(workspace, role=15)

        response = client.post(installation_url(workspace), {}, format="json")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["code"] == "runner_not_found"

        missing = client.post(
            "/api/workspaces/runner-workspace-does-not-exist/runner/installation/",
            {},
            format="json",
        )
        assert missing.status_code == response.status_code
        assert missing.data == response.data

    @pytest.mark.django_db
    def test_membership_revoked_before_service_authorization_is_rejected(self, workspace, create_user):
        membership = WorkspaceMember.objects.get(workspace=workspace, member=create_user)
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        with pytest.raises(RunnerPermissionError, match="Admin"):
            RunnerInstallationService.activate(
                workspace=workspace,
                actor=create_user,
                **activation_payload(),
            )

    @pytest.mark.django_db
    def test_user_throttle_cannot_be_bypassed_by_rotating_workspace_slugs(self, session_client, mocker):
        cache.clear()
        mocker.patch.object(RunnerUserMutationThrottle, "get_rate", return_value="1/minute")

        first = session_client.post(
            "/api/workspaces/missing-runner-one/runner/installation/",
            activation_payload(),
            format="json",
        )
        throttled = session_client.post(
            "/api/workspaces/missing-runner-two/runner/installation/",
            activation_payload(),
            format="json",
        )

        assert first.status_code == status.HTTP_404_NOT_FOUND
        assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        cache.clear()


@pytest.mark.usefixtures("runner_enabled")
@pytest.mark.contract
class TestRunnerInstallationLifecycle:
    @pytest.mark.django_db
    def test_admin_reads_non_persisted_inactive_state(self, session_client, workspace):
        response = session_client.get(installation_url(workspace))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["state"] == "inactive"
        assert response.data["lifecycle_state"] is None
        assert response.data["required_consent_version"] == CURRENT_RUNNER_CONSENT.version
        assert response.data["required_consent_digest"] == CURRENT_RUNNER_CONSENT.digest
        assert response.data["required_consent_text"] == RUNNER_CONSENT_TEXT
        assert response.data["consent_required"] is True
        assert response.data["is_effectively_active"] is False
        assert response.data["id"] is None
        assert not RunnerInstallation.objects.exists()

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            (
                {
                    "consent_version": CURRENT_RUNNER_CONSENT.version + 1,
                    "consent_digest": CURRENT_RUNNER_CONSENT.digest,
                },
                "code",
            ),
            (
                {
                    "consent_version": CURRENT_RUNNER_CONSENT.version,
                    "consent_digest": "0" * 64,
                },
                "code",
            ),
            ({"consent_version": CURRENT_RUNNER_CONSENT.version}, "consent_digest"),
        ],
    )
    def test_activation_requires_exact_current_consent(self, session_client, workspace, payload, field):
        response = session_client.post(installation_url(workspace), payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field in response.data
        assert not RunnerInstallation.objects.exists()
        assert not RunnerAuditEvent.objects.exists()

    @pytest.mark.django_db
    def test_activation_is_idempotent_and_audited_once(self, session_client, workspace, create_user):
        created = session_client.post(
            installation_url(workspace),
            activation_payload(),
            format="json",
            HTTP_X_REQUEST_ID="runner-test-request-1",
            HTTP_USER_AGENT="Hangar contract test\nignored-control",
            REMOTE_ADDR="192.0.2.10",
        )
        repeated = session_client.post(installation_url(workspace), activation_payload(), format="json")

        assert created.status_code == status.HTTP_201_CREATED
        assert repeated.status_code == status.HTTP_200_OK
        assert created.data["id"] == repeated.data["id"]
        assert repeated.data["state"] == "active"
        assert repeated.data["lifecycle_state"] == "active"
        assert repeated.data["is_effectively_active"] is True
        installation = RunnerInstallation.objects.get(workspace=workspace)
        assert installation.activated_by == create_user.id
        event = RunnerAuditEvent.objects.get(
            workspace_id=workspace.id,
            action=RunnerAuditAction.INSTALLATION_ACTIVATED,
        )
        assert event.actor_id == create_user.id
        assert event.schema_version == 1
        assert event.request_id == "runner-test-request-1"
        assert event.source_ip == "192.0.2.10"
        assert event.user_agent == "Hangar contract testignored-control"
        assert event.metadata["previous_state"] == "inactive"
        assert event.metadata["state"] == "active"
        assert event.metadata["consent_digest"] == CURRENT_RUNNER_CONSENT.digest
        assert RunnerAuditEvent.objects.count() == 1

    @pytest.mark.django_db
    def test_mutations_are_throttled_per_user_and_workspace(self, session_client, workspace, mocker):
        cache.clear()
        mocker.patch.object(RunnerMutationThrottle, "get_rate", return_value="1/minute")

        first = session_client.post(installation_url(workspace), activation_payload(), format="json")
        throttled = session_client.post(installation_url(workspace), activation_payload(), format="json")

        assert first.status_code == status.HTTP_201_CREATED
        assert throttled.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        cache.clear()

    @pytest.mark.django_db
    def test_suspend_then_reactivate_records_each_transition(self, session_client, workspace):
        session_client.post(installation_url(workspace), activation_payload(), format="json")

        suspended = session_client.post(suspend_url(workspace), {}, format="json")
        repeated_suspend = session_client.post(suspend_url(workspace), {}, format="json")
        reactivated = session_client.post(installation_url(workspace), activation_payload(), format="json")

        assert suspended.status_code == status.HTTP_200_OK
        assert suspended.data["state"] == "suspended"
        assert suspended.data["is_effectively_active"] is False
        assert repeated_suspend.status_code == status.HTTP_200_OK
        assert reactivated.status_code == status.HTTP_200_OK
        assert reactivated.data["state"] == "active"
        assert RunnerAuditEvent.objects.filter(workspace_id=workspace.id).count() == 3
        assert list(
            RunnerAuditEvent.objects.filter(workspace_id=workspace.id)
            .order_by("created_at")
            .values_list("action", flat=True)
        ) == [
            RunnerAuditAction.INSTALLATION_ACTIVATED,
            RunnerAuditAction.INSTALLATION_SUSPENDED,
            RunnerAuditAction.INSTALLATION_REACTIVATED,
        ]

    @pytest.mark.django_db
    def test_obsolete_consent_blocks_effective_activation_until_renewed(self, session_client, workspace):
        session_client.post(installation_url(workspace), activation_payload(), format="json")
        RunnerInstallation.objects.filter(workspace=workspace).update(
            consent_document="obsolete-consent-v0",
            consent_digest="0" * 64,
        )

        stale = session_client.get(installation_url(workspace))

        assert stale.status_code == status.HTTP_200_OK
        assert stale.data["state"] == "consent_required"
        assert stale.data["lifecycle_state"] == "active"
        assert stale.data["consent_required"] is True
        assert stale.data["is_effectively_active"] is False
        with pytest.raises(RunnerTransitionError, match="current consent"):
            RunnerInstallationService.require_effectively_active(workspace=workspace)

        renewed = session_client.post(installation_url(workspace), activation_payload(), format="json")

        assert renewed.status_code == status.HTTP_200_OK
        assert renewed.data["state"] == "active"
        assert renewed.data["consent_required"] is False
        assert RunnerAuditEvent.objects.filter(action=RunnerAuditAction.CONSENT_RENEWED).count() == 1

    @pytest.mark.django_db
    def test_revocation_is_terminal(self, session_client, workspace):
        session_client.post(installation_url(workspace), activation_payload(), format="json")

        revoked = session_client.post(revoke_url(workspace), {}, format="json")
        repeated_revoke = session_client.post(revoke_url(workspace), {}, format="json")
        reactivation = session_client.post(installation_url(workspace), activation_payload(), format="json")

        assert revoked.status_code == status.HTTP_200_OK
        assert revoked.data["state"] == "revoked"
        assert repeated_revoke.status_code == status.HTTP_200_OK
        assert reactivation.status_code == status.HTTP_409_CONFLICT
        assert reactivation.data["code"] == "invalid_runner_transition"
        assert RunnerInstallation.objects.get(workspace=workspace).state == RunnerInstallationState.REVOKED
        assert RunnerAuditEvent.objects.filter(workspace_id=workspace.id).count() == 2

    @pytest.mark.django_db
    def test_suspend_before_activation_is_rejected(self, session_client, workspace):
        response = session_client.post(suspend_url(workspace), {}, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data["code"] == "invalid_runner_transition"


@pytest.mark.usefixtures("runner_enabled")
@pytest.mark.contract
@pytest.mark.runner_migrations
class TestRunnerDatabaseIntegrity:
    @pytest.mark.django_db(transaction=True)
    def test_additive_migration_upgrades_foundation_rows(self, workspace, create_user, request):
        if (
            request.config.getoption("nomigrations")
            or "django_migrations" not in connection.introspection.table_names()
        ):
            pytest.skip("upgrade-path test requires pytest --migrations")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
                ["ext", "0005_runner_foundation_hardening"],
            )
            if cursor.fetchone() is None:
                pytest.skip("upgrade-path test requires pytest --migrations")

        second_workspace = Workspace.objects.create(
            name="Runner migration workspace",
            slug=f"runner-migration-{uuid4().hex[:8]}",
            owner=create_user,
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("ext", "0004_runner_foundation")])
        legacy_apps = executor.loader.project_state([("ext", "0004_runner_foundation")]).apps
        LegacyInstallation = legacy_apps.get_model("ext", "RunnerInstallation")
        LegacyAuditEvent = legacy_apps.get_model("ext", "RunnerAuditEvent")

        LegacyInstallation.objects.create(workspace_id=workspace.id, state="inactive")
        active = LegacyInstallation.objects.create(
            workspace_id=second_workspace.id,
            state="active",
            consent_version=1,
            activated_by_id=create_user.id,
            activated_at=timezone.now(),
            created_by_id=create_user.id,
            updated_by_id=create_user.id,
        )
        legacy_event = LegacyAuditEvent.objects.create(
            workspace_id=second_workspace.id,
            actor_id=create_user.id,
            action=RunnerAuditAction.INSTALLATION_ACTIVATED,
            target_type="runner_installation",
            target_id=active.id,
            metadata=["legacy"],
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("ext", "0005_runner_foundation_hardening")])

        try:
            assert not RunnerInstallation.objects.filter(workspace_id=workspace.id).exists()
            upgraded = RunnerInstallation.objects.get(workspace_id=second_workspace.id)
            assert upgraded.consent_document == CURRENT_RUNNER_CONSENT.document_id
            assert upgraded.consent_digest == CURRENT_RUNNER_CONSENT.digest
            assert upgraded.activated_by == create_user.id
            event = RunnerAuditEvent.objects.get(pk=legacy_event.id)
            assert event.workspace_id == second_workspace.id
            assert event.actor_id == create_user.id
            assert event.request_id == f"migration:{event.id}"
            assert event.metadata == {"legacy_metadata": ["legacy"]}
        finally:
            with connection.cursor() as cursor:
                cursor.execute("ALTER TABLE ext_runner_audit_events DISABLE TRIGGER ext_runner_audit_events_immutable")
                cursor.execute("DELETE FROM ext_runner_audit_events WHERE id = %s", [legacy_event.id])
                cursor.execute("ALTER TABLE ext_runner_audit_events ENABLE TRIGGER ext_runner_audit_events_immutable")

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "overrides",
        [
            {"state": "unknown"},
            {"state": RunnerInstallationState.SUSPENDED},
            {"state": RunnerInstallationState.REVOKED},
            {"consent_digest": ""},
            {"consent_digest": "0" * 63},
            {"consent_digest": "A" * 64},
        ],
    )
    def test_database_rejects_invalid_lifecycle_states(self, workspace, create_user, overrides):
        fields = {
            "workspace": workspace,
            "state": RunnerInstallationState.ACTIVE,
            "consent_version": CURRENT_RUNNER_CONSENT.version,
            "consent_document": CURRENT_RUNNER_CONSENT.document_id,
            "consent_digest": CURRENT_RUNNER_CONSENT.digest,
            "activated_by": create_user.id,
            "activated_at": timezone.now(),
        }
        fields.update(overrides)

        with pytest.raises(IntegrityError), transaction.atomic():
            RunnerInstallation.objects.create(**fields)

    @pytest.mark.django_db
    def test_state_and_audit_write_roll_back_together(self, workspace, create_user, mocker):
        mocker.patch.object(
            RunnerInstallationService,
            "_audit",
            side_effect=RuntimeError("audit unavailable"),
        )

        with pytest.raises(RuntimeError, match="audit unavailable"):
            RunnerInstallationService.activate(
                workspace=workspace,
                actor=create_user,
                **activation_payload(),
            )

        assert not RunnerInstallation.objects.exists()
        assert not RunnerAuditEvent.objects.exists()

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "overrides",
        [
            {"target_id": None},
            {"request_id": ""},
        ],
    )
    def test_database_rejects_incomplete_audit_evidence(self, workspace, create_user, overrides):
        fields = {
            "workspace_id": workspace.id,
            "actor_id": create_user.id,
            "action": RunnerAuditAction.INSTALLATION_ACTIVATED,
            "target_type": "runner_installation",
            "target_id": uuid4(),
            "request_id": str(uuid4()),
            "metadata": {},
        }
        fields.update(overrides)

        with pytest.raises(IntegrityError), transaction.atomic():
            RunnerAuditEvent.objects.bulk_create([RunnerAuditEvent(**fields)])

    @pytest.mark.django_db
    def test_audit_metadata_is_guarded_by_model_and_database(self, workspace, create_user):
        fields = {
            "workspace_id": workspace.id,
            "actor_id": create_user.id,
            "action": RunnerAuditAction.INSTALLATION_ACTIVATED,
            "target_type": "runner_installation",
            "target_id": uuid4(),
            "request_id": str(uuid4()),
            "metadata": [],
        }

        with pytest.raises(ValidationError, match="must be an object"):
            RunnerAuditEvent.objects.create(**fields)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_constraint WHERE conname = %s",
                ["ext_runner_audit_metadata_object"],
            )
            if cursor.fetchone() is None:
                pytest.skip("database metadata constraint requires pytest --migrations")
        with pytest.raises(IntegrityError), transaction.atomic():
            RunnerAuditEvent.objects.bulk_create([RunnerAuditEvent(**fields)])

    @pytest.mark.django_db
    def test_audit_event_is_guarded_by_model_and_database(self, session_client, workspace):
        session_client.post(installation_url(workspace), activation_payload(), format="json")
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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_trigger WHERE tgname = %s AND NOT tgisinternal",
                ["ext_runner_audit_events_immutable"],
            )
            if cursor.fetchone() is None:
                pytest.skip("database trigger requires pytest --migrations")
        with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE ext_runner_audit_events SET metadata = '{}' WHERE id = %s",
                    [event.id],
                )

    @pytest.mark.django_db
    def test_audit_attribution_survives_actor_and_workspace_deletion(self, session_client, workspace, create_user):
        session_client.post(installation_url(workspace), activation_payload(), format="json")
        event_id = RunnerAuditEvent.objects.get().id
        workspace_id = workspace.id
        actor_id = create_user.id

        User.objects.filter(pk=create_user.id).delete()

        event = RunnerAuditEvent.objects.get(pk=event_id)
        assert event.workspace_id == workspace_id
        assert event.actor_id == actor_id
        assert not RunnerInstallation.objects.filter(workspace_id=workspace_id).exists()

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_activation_creates_one_installation_and_one_audit_event(self, workspace, create_user):
        barrier = Barrier(2)

        def activate():
            close_old_connections()
            try:
                thread_workspace = Workspace.objects.get(pk=workspace.id)
                thread_actor = User.objects.get(pk=create_user.id)
                barrier.wait(timeout=5)
                return RunnerInstallationService.activate(
                    workspace=thread_workspace,
                    actor=thread_actor,
                    **activation_payload(),
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: activate(), range(2)))

        assert sorted(result.created for result in results) == [False, True]
        assert RunnerInstallation.objects.filter(workspace=workspace).count() == 1
        assert RunnerAuditEvent.objects.filter(workspace_id=workspace.id).count() == 1
