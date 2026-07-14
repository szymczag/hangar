# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.db import migrations, models


RUNNER_CONSENT_V1_DOCUMENT = "hangar-runner-security-consent-v1"
RUNNER_CONSENT_V1_DIGEST = "6713ce3d0b6f6e37853b7d4892484264c790a9bda76decf76fc3a1dc3aaa9fcf"
RUNNER_AUDIT_ACTIONS = (
    "runner.installation.activated",
    "runner.installation.reactivated",
    "runner.installation.consent_renewed",
    "runner.installation.suspended",
    "runner.installation.revoked",
)


def harden_runner_foundation_data(apps, _schema_editor):
    RunnerInstallation = apps.get_model("ext", "RunnerInstallation")
    RunnerAuditEvent = apps.get_model("ext", "RunnerAuditEvent")

    RunnerInstallation.objects.filter(deleted_at__isnull=False).delete()
    RunnerInstallation.objects.filter(state="inactive").delete()

    for installation in RunnerInstallation.objects.all().iterator():
        if installation.state not in {"active", "suspended", "revoked"}:
            raise RuntimeError(f"Unsupported Runner installation state: {installation.state}")
        if installation.consent_version not in {0, 1}:
            raise RuntimeError(
                f"Runner installation {installation.id} has an unknown consent version: {installation.consent_version}"
            )

        activated_by = installation.activated_by or installation.created_by_id or installation.updated_by_id
        if activated_by is None:
            raise RuntimeError(f"Runner installation {installation.id} has no recoverable activation actor")

        installation.consent_version = 1
        installation.consent_document = RUNNER_CONSENT_V1_DOCUMENT
        installation.consent_digest = RUNNER_CONSENT_V1_DIGEST
        installation.activated_by = activated_by
        installation.activated_at = installation.activated_at or installation.created_at

        if installation.state == "active":
            installation.suspended_by = None
            installation.suspended_at = None
            installation.revoked_by = None
            installation.revoked_at = None
        elif installation.state == "suspended":
            installation.suspended_by = installation.suspended_by or activated_by
            installation.suspended_at = installation.suspended_at or installation.updated_at
            installation.revoked_by = None
            installation.revoked_at = None
        else:
            if (installation.suspended_by is None) != (installation.suspended_at is None):
                installation.suspended_by = None
                installation.suspended_at = None
            installation.revoked_by = installation.revoked_by or installation.suspended_by or activated_by
            installation.revoked_at = installation.revoked_at or installation.updated_at

        installation.save(
            update_fields=[
                "state",
                "consent_version",
                "consent_document",
                "consent_digest",
                "activated_by",
                "activated_at",
                "suspended_by",
                "suspended_at",
                "revoked_by",
                "revoked_at",
            ]
        )

    for event in RunnerAuditEvent.objects.all().iterator():
        if event.actor_id is None:
            raise RuntimeError(f"Runner audit event {event.id} has no recoverable actor evidence")
        if event.target_id is None:
            raise RuntimeError(f"Runner audit event {event.id} has no target evidence")
        if event.action not in RUNNER_AUDIT_ACTIONS:
            raise RuntimeError(f"Runner audit event {event.id} has an unsupported action: {event.action}")
        if event.target_type != "runner_installation":
            raise RuntimeError(f"Runner audit event {event.id} has an unsupported target: {event.target_type}")

        event.request_id = f"migration:{event.id}"
        if not isinstance(event.metadata, dict):
            event.metadata = {"legacy_metadata": event.metadata}
        event.save(update_fields=["request_id", "metadata"])


class Migration(migrations.Migration):
    dependencies = [("ext", "0004_runner_foundation")]

    operations = [
        migrations.RemoveConstraint(
            model_name="runnerinstallation",
            name="ext_runner_active_requires_consent",
        ),
        migrations.AddField(
            model_name="runnerinstallation",
            name="consent_document",
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="runnerinstallation",
            name="consent_digest",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="activated_by",
            field=models.UUIDField(null=True),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="suspended_by",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="revoked_by",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.RemoveIndex(
            model_name="runnerauditevent",
            name="ext_runner__workspa_1ee13e_idx",
        ),
        migrations.RenameField(
            model_name="runnerauditevent",
            old_name="workspace",
            new_name="workspace_id",
        ),
        migrations.RenameField(
            model_name="runnerauditevent",
            old_name="actor",
            new_name="actor_id",
        ),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="workspace_id",
            field=models.UUIDField(db_index=True),
        ),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="actor_id",
            field=models.UUIDField(db_index=True, null=True),
        ),
        migrations.AddIndex(
            model_name="runnerauditevent",
            index=models.Index(
                fields=["workspace_id", "created_at"],
                name="ext_runner__workspa_1ee13e_idx",
            ),
        ),
        migrations.AddField(
            model_name="runnerauditevent",
            name="schema_version",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="runnerauditevent",
            name="request_id",
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.AddField(
            model_name="runnerauditevent",
            name="source_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="runnerauditevent",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.RunPython(harden_runner_foundation_data, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="state",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("suspended", "Suspended"),
                    ("revoked", "Revoked"),
                ],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="consent_version",
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="consent_document",
            field=models.CharField(max_length=128),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="consent_digest",
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="activated_by",
            field=models.UUIDField(),
        ),
        migrations.AlterField(
            model_name="runnerinstallation",
            name="activated_at",
            field=models.DateTimeField(),
        ),
        migrations.RemoveField(model_name="runnerinstallation", name="deleted_at"),
        migrations.RemoveField(model_name="runnerinstallation", name="created_by"),
        migrations.RemoveField(model_name="runnerinstallation", name="updated_by"),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("runner.installation.activated", "Installation activated"),
                    ("runner.installation.reactivated", "Installation reactivated"),
                    ("runner.installation.consent_renewed", "Consent renewed"),
                    ("runner.installation.suspended", "Installation suspended"),
                    ("runner.installation.revoked", "Installation revoked"),
                ],
                max_length=96,
            ),
        ),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="target_type",
            field=models.CharField(
                choices=[("runner_installation", "Runner installation")],
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="target_id",
            field=models.UUIDField(),
        ),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="actor_id",
            field=models.UUIDField(db_index=True),
        ),
        migrations.AlterField(
            model_name="runnerauditevent",
            name="request_id",
            field=models.CharField(max_length=128),
        ),
        migrations.AddConstraint(
            model_name="runnerinstallation",
            constraint=models.CheckConstraint(
                check=models.Q(state__in=["active", "suspended", "revoked"]),
                name="ext_runner_installation_valid_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerinstallation",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(consent_version__gte=1) & ~models.Q(consent_document="") & ~models.Q(consent_digest="")
                ),
                name="ext_runner_installation_consent",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerinstallation",
            constraint=models.CheckConstraint(
                check=models.Q(consent_digest__regex="^[0-9a-f]{64}$"),
                name="ext_runner_installation_consent_digest",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerinstallation",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(state="active", suspended_by__isnull=True, suspended_at__isnull=True)
                    | models.Q(state="suspended", suspended_by__isnull=False, suspended_at__isnull=False)
                    | (
                        models.Q(state="revoked")
                        & (
                            models.Q(suspended_by__isnull=True, suspended_at__isnull=True)
                            | models.Q(suspended_by__isnull=False, suspended_at__isnull=False)
                        )
                    )
                ),
                name="ext_runner_installation_suspension",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerinstallation",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(state="revoked", revoked_by__isnull=False, revoked_at__isnull=False)
                    | (~models.Q(state="revoked") & models.Q(revoked_by__isnull=True, revoked_at__isnull=True))
                ),
                name="ext_runner_installation_revocation",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerauditevent",
            constraint=models.CheckConstraint(
                check=models.Q(action__in=list(RUNNER_AUDIT_ACTIONS)),
                name="ext_runner_audit_valid_action",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerauditevent",
            constraint=models.CheckConstraint(
                check=models.Q(target_type__in=["runner_installation"]),
                name="ext_runner_audit_valid_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerauditevent",
            constraint=models.CheckConstraint(
                check=models.Q(schema_version__gte=1),
                name="ext_runner_audit_schema_version",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerauditevent",
            constraint=models.CheckConstraint(
                check=models.Q(request_id__regex="^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"),
                name="ext_runner_audit_request_id",
            ),
        ),
        migrations.RunSQL(
            sql="""
                ALTER TABLE ext_runner_audit_events
                ADD CONSTRAINT ext_runner_audit_metadata_object
                CHECK (jsonb_typeof(metadata) = 'object');
            """,
            reverse_sql="""
                ALTER TABLE ext_runner_audit_events
                DROP CONSTRAINT IF EXISTS ext_runner_audit_metadata_object;
            """,
        ),
        migrations.RunSQL(
            sql="""
                CREATE FUNCTION ext_runner_audit_events_reject_mutation()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    RAISE EXCEPTION 'ext_runner_audit_events is append-only'
                        USING ERRCODE = '55000';
                END;
                $$;
            """,
            reverse_sql="DROP FUNCTION IF EXISTS ext_runner_audit_events_reject_mutation();",
        ),
        migrations.RunSQL(
            sql="""
                CREATE TRIGGER ext_runner_audit_events_immutable
                BEFORE UPDATE OR DELETE ON ext_runner_audit_events
                FOR EACH ROW
                EXECUTE FUNCTION ext_runner_audit_events_reject_mutation();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS ext_runner_audit_events_immutable
                ON ext_runner_audit_events;
            """,
        ),
    ]
