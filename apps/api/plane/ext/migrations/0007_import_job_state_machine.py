# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from hashlib import sha256
import json
import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone
import django.db.models.deletion


TERMINAL_STATUSES = {"completed", "completed_with_errors", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "processing"}


def harden_existing_import_jobs(apps, _schema_editor):
    ImportJob = apps.get_model("ext", "ImportJob")
    now = timezone.now()
    # Historical migration models do not retain BaseModel's runtime
    # ``all_objects`` manager. Their default manager is unfiltered and includes
    # soft-deleted rows, which is required for a complete invariant upgrade.
    for job in ImportJob.objects.all().iterator():
        if len(job.source_digest) != 64 or any(character not in "0123456789abcdef" for character in job.source_digest):
            raise RuntimeError(f"Import job {job.id} has an invalid source digest")
        manifest = {
            "config": job.config if isinstance(job.config, dict) else {},
            "initiated_by_id": str(job.initiated_by_id) if job.initiated_by_id else None,
            "project_id": str(job.project_id),
            "provider": job.provider,
            "source_digest": job.source_digest,
            "workspace_id": str(job.workspace_id),
        }
        canonical = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        job.manifest_digest = sha256(canonical.encode("utf-8")).hexdigest()
        job.idempotency_namespace = uuid.uuid4()
        job.lease_token = None
        job.lease_expires_at = None

        if job.status in ACTIVE_STATUSES:
            job.status = "failed"
            job.reason = "security_upgrade_required"
            job.config = {}
            job.completed_at = now
            job.celery_task_id = ""
            job.quota_released_at = now
        elif job.status in TERMINAL_STATUSES:
            job.completed_at = job.completed_at or job.updated_at or job.created_at or now
            job.celery_task_id = ""
            job.quota_released_at = job.quota_released_at or job.completed_at
        else:
            raise RuntimeError(f"Import job {job.id} has an unsupported status: {job.status}")
        job.save()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ext", "0006_import_job"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="importjob",
            name="ext_imp_one_active_per_project",
        ),
        migrations.AddField(
            model_name="importjob",
            name="execution_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="idempotency_namespace",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False),
        ),
        migrations.AddField(
            model_name="importjob",
            name="lease_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="lease_token",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="manifest_digest",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="queued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="quota_released_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="retention_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="retry_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="retry_jobs",
                to="ext.importjob",
            ),
        ),
        migrations.AlterField(
            model_name="importjob",
            name="status",
            field=models.CharField(
                choices=[
                    ("preparing", "Preparing"),
                    ("queued", "Queued"),
                    ("processing", "Processing"),
                    ("cancelling", "Cancelling"),
                    ("completed", "Completed"),
                    ("completed_with_errors", "Completed with errors"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                ],
                default="preparing",
                max_length=32,
            ),
        ),
        migrations.RunPython(harden_existing_import_jobs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="importjob",
            name="manifest_digest",
            field=models.CharField(max_length=64),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.UniqueConstraint(
                condition=Q(status__in=["preparing", "queued", "processing", "cancelling"]),
                fields=("project",),
                name="ext_imp_one_active_per_project",
            ),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.CheckConstraint(
                check=Q(
                    status__in=[
                        "preparing",
                        "queued",
                        "processing",
                        "cancelling",
                        "completed",
                        "completed_with_errors",
                        "failed",
                        "cancelled",
                    ]
                ),
                name="ext_imp_valid_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.CheckConstraint(
                check=Q(source_digest__regex=r"^[0-9a-f]{64}$"),
                name="ext_imp_source_digest_sha256",
            ),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.CheckConstraint(
                check=Q(manifest_digest__regex=r"^[0-9a-f]{64}$"),
                name="ext_imp_manifest_digest_sha256",
            ),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.CheckConstraint(
                check=(
                    ~Q(status="processing")
                    | Q(
                        lease_token__isnull=False,
                        lease_expires_at__isnull=False,
                        started_at__isnull=False,
                    )
                    & ~Q(celery_task_id="")
                ),
                name="ext_imp_processing_has_lease",
            ),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.CheckConstraint(
                check=(
                    ~Q(status__in=["completed", "completed_with_errors", "failed", "cancelled"])
                    | Q(
                        completed_at__isnull=False,
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                    )
                ),
                name="ext_imp_terminal_is_fenced",
            ),
        ),
        migrations.AddConstraint(
            model_name="importjob",
            constraint=models.CheckConstraint(
                check=(
                    Q(queued_at__isnull=True)
                    | Q(retention_expires_at__isnull=True)
                    | Q(retention_expires_at__gte=F("queued_at"))
                ),
                name="ext_imp_valid_retention",
            ),
        ),
        migrations.CreateModel(
            name="ImportAuditEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("workspace_id", models.UUIDField(db_index=True)),
                ("project_id", models.UUIDField(db_index=True)),
                ("job_id", models.UUIDField(db_index=True)),
                ("actor_id", models.UUIDField(blank=True, db_index=True, null=True)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("import.created", "Created"),
                            ("import.source_stored", "Source stored"),
                            ("import.dispatch_attempted", "Dispatch attempted"),
                            ("import.claimed", "Claimed"),
                            ("import.lease_recovered", "Lease recovered"),
                            ("import.retry_scheduled", "Retry scheduled"),
                            ("import.cancellation_requested", "Cancellation requested"),
                            ("import.authorization_revoked", "Authorization revoked"),
                            ("import.decision_drift", "Decision drift"),
                            ("import.quota_rejected", "Quota rejected"),
                            ("import.terminalized", "Terminalized"),
                            ("import.source_deleted", "Source deleted"),
                            ("import.cleanup_failed", "Cleanup failed"),
                        ],
                        max_length=64,
                    ),
                ),
                ("previous_status", models.CharField(blank=True, max_length=32)),
                ("resulting_status", models.CharField(max_length=32)),
                ("execution_generation", models.PositiveBigIntegerField(default=0)),
                ("request_id", models.CharField(max_length=128)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ext_import_audit_events",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["workspace_id", "created_at"], name="ext_imp_audit_ws_time_idx"),
                    models.Index(fields=["action", "created_at"], name="ext_imp_audit_action_time_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        check=Q(
                            action__in=[
                                "import.created",
                                "import.source_stored",
                                "import.dispatch_attempted",
                                "import.claimed",
                                "import.lease_recovered",
                                "import.retry_scheduled",
                                "import.cancellation_requested",
                                "import.authorization_revoked",
                                "import.decision_drift",
                                "import.quota_rejected",
                                "import.terminalized",
                                "import.source_deleted",
                                "import.cleanup_failed",
                            ]
                        ),
                        name="ext_imp_audit_valid_action",
                    ),
                    models.CheckConstraint(
                        check=Q(request_id__regex=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"),
                        name="ext_imp_audit_request_id",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ImportDispatch",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("generation", models.PositiveBigIntegerField()),
                ("task_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("published", "Published"),
                            ("consumed", "Consumed"),
                            ("superseded", "Superseded"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("available_at", models.DateTimeField(default=timezone.now)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("publish_attempts", models.PositiveSmallIntegerField(default=0)),
                (
                    "last_error_code",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "None"),
                            ("broker_unavailable", "Broker unavailable"),
                            ("publish_confirmation_unknown", "Publish confirmation unknown"),
                        ],
                        default="",
                        max_length=40,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dispatches",
                        to="ext.importjob",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "db_table": "ext_import_dispatches",
                "ordering": ("created_at",),
                "indexes": [
                    models.Index(fields=["state", "available_at"], name="ext_imp_dispatch_ready_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("job", "generation"),
                        name="ext_imp_dispatch_job_generation",
                    ),
                    models.CheckConstraint(
                        check=Q(state__in=["pending", "published", "consumed", "superseded"]),
                        name="ext_imp_dispatch_valid_state",
                    ),
                    models.CheckConstraint(
                        check=Q(publish_attempts__lte=100),
                        name="ext_imp_dispatch_attempt_limit",
                    ),
                    models.CheckConstraint(
                        check=(
                            Q(state="pending", published_at__isnull=True, consumed_at__isnull=True)
                            | Q(state="published", published_at__isnull=False, consumed_at__isnull=True)
                            | Q(state="consumed", published_at__isnull=False, consumed_at__isnull=False)
                            | Q(state="superseded", consumed_at__isnull=True)
                        ),
                        name="ext_imp_dispatch_state_times",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql="""
                CREATE OR REPLACE FUNCTION ext_reject_import_audit_mutation()
                RETURNS trigger AS $$
                BEGIN
                    RAISE EXCEPTION 'import audit events are immutable';
                END;
                $$ LANGUAGE plpgsql;

                CREATE TRIGGER ext_import_audit_immutable
                BEFORE UPDATE OR DELETE ON ext_import_audit_events
                FOR EACH ROW EXECUTE FUNCTION ext_reject_import_audit_mutation();
            """,
            reverse_sql="""
                DROP TRIGGER IF EXISTS ext_import_audit_immutable ON ext_import_audit_events;
                DROP FUNCTION IF EXISTS ext_reject_import_audit_mutation();
            """,
        ),
    ]
