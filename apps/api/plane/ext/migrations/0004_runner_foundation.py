# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0121_alter_estimate_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("ext", "0003_issue_worklog"),
    ]

    operations = [
        migrations.CreateModel(
            name="RunnerInstallation",
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
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("inactive", "Inactive"),
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("revoked", "Revoked"),
                        ],
                        default="inactive",
                        max_length=16,
                    ),
                ),
                ("consent_version", models.PositiveSmallIntegerField(default=0)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("suspended_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "activated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="runner_installations_activated",
                        to=settings.AUTH_USER_MODEL,
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
                    "revoked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="runner_installations_revoked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "suspended_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="runner_installations_suspended",
                        to=settings.AUTH_USER_MODEL,
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
                "indexes": [models.Index(fields=["state", "updated_at"], name="ext_runner__state_4eccb3_idx")],
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
                ("action", models.CharField(max_length=96)),
                ("target_type", models.CharField(max_length=64)),
                ("target_id", models.UUIDField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="runner_audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runner_audit_events",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "db_table": "ext_runner_audit_events",
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(fields=["workspace", "created_at"], name="ext_runner__workspa_1ee13e_idx"),
                    models.Index(fields=["action", "created_at"], name="ext_runner__action_f9edf5_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="runnerinstallation",
            constraint=models.CheckConstraint(
                check=(
                    ~models.Q(state="active")
                    | (models.Q(consent_version__gte=1) & models.Q(activated_at__isnull=False))
                ),
                name="ext_runner_active_requires_consent",
            ),
        ),
    ]
