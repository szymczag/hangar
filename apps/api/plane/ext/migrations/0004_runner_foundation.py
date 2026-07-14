# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0121_alter_estimate_type"),
        ("ext", "0003_issue_worklog"),
    ]

    operations = [
        migrations.CreateModel(
            name="RunnerInstallation",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("revoked", "Revoked"),
                        ],
                        max_length=16,
                    ),
                ),
                ("consent_version", models.PositiveSmallIntegerField()),
                ("consent_document", models.CharField(max_length=128)),
                ("consent_digest", models.CharField(max_length=64)),
                ("activated_by", models.UUIDField()),
                ("activated_at", models.DateTimeField()),
                ("suspended_by", models.UUIDField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_by", models.UUIDField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "workspace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runner_installation",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_runner_installations",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(
                        fields=["state", "updated_at"],
                        name="ext_runner__state_4eccb3_idx",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="RunnerAuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("workspace_id", models.UUIDField(db_index=True)),
                ("actor_id", models.UUIDField(db_index=True)),
                (
                    "action",
                    models.CharField(
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
                (
                    "target_type",
                    models.CharField(
                        choices=[("runner_installation", "Runner installation")],
                        max_length=64,
                    ),
                ),
                ("target_id", models.UUIDField(blank=True, null=True)),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ext_runner_audit_events",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(
                        fields=["workspace_id", "created_at"],
                        name="ext_runner__workspa_1ee13e_idx",
                    ),
                    models.Index(
                        fields=["action", "created_at"],
                        name="ext_runner__action_f9edf5_idx",
                    ),
                ],
            },
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
                    models.Q(
                        state="active",
                        suspended_by__isnull=True,
                        suspended_at__isnull=True,
                    )
                    | models.Q(
                        state="suspended",
                        suspended_by__isnull=False,
                        suspended_at__isnull=False,
                    )
                    | (
                        models.Q(state="revoked")
                        & (
                            models.Q(
                                suspended_by__isnull=True,
                                suspended_at__isnull=True,
                            )
                            | models.Q(
                                suspended_by__isnull=False,
                                suspended_at__isnull=False,
                            )
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
                    models.Q(
                        state="revoked",
                        revoked_by__isnull=False,
                        revoked_at__isnull=False,
                    )
                    | (~models.Q(state="revoked") & models.Q(revoked_by__isnull=True, revoked_at__isnull=True))
                ),
                name="ext_runner_installation_revocation",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerauditevent",
            constraint=models.CheckConstraint(
                check=models.Q(
                    action__in=[
                        "runner.installation.activated",
                        "runner.installation.reactivated",
                        "runner.installation.consent_renewed",
                        "runner.installation.suspended",
                        "runner.installation.revoked",
                    ]
                ),
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
                check=models.Q(
                    target_type="runner_installation",
                    target_id__isnull=False,
                ),
                name="ext_runner_audit_target_id",
            ),
        ),
        migrations.AddConstraint(
            model_name="runnerauditevent",
            constraint=models.CheckConstraint(
                check=models.Q(schema_version__gte=1),
                name="ext_runner_audit_schema_version",
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
