# Generated for Hangar secure email delivery.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def audit_fields():
    return [
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
        ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
        ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
        ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
    ]


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("db", "0121_alter_estimate_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserOpenPGPKey",
            fields=audit_fields()
            + [
                ("version", models.PositiveIntegerField()),
                ("certificate_ciphertext", models.TextField()),
                ("primary_fingerprint", models.CharField(db_index=True, max_length=64)),
                ("encryption_subkey_fingerprint", models.CharField(max_length=64)),
                ("primary_algorithm", models.CharField(max_length=64)),
                ("encryption_algorithm", models.CharField(max_length=64)),
                ("encryption_key_size", models.PositiveIntegerField(blank=True, null=True)),
                ("key_created_at", models.DateTimeField(blank=True, null=True)),
                ("key_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_validated_at", models.DateTimeField(blank=True, null=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("replaced_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending verification"),
                            ("active", "Active"),
                            ("replaced", "Replaced"),
                            ("revoked", "Revoked"),
                            ("expired", "Expired"),
                            ("invalid", "Invalid"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
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
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="openpgp_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "user_openpgp_keys", "ordering": ("-version",)},
        ),
        migrations.CreateModel(
            name="OpenPGPKeyChallenge",
            fields=audit_fields()
            + [
                ("token_digest", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
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
                    "key",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="challenges",
                        to="db.useropenpgpkey",
                    ),
                ),
            ],
            options={"db_table": "openpgp_key_challenges", "ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="EmailOutbox",
            fields=audit_fields()
            + [
                ("recipient_email_ciphertext", models.TextField()),
                ("recipient_email_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "policy_class",
                    models.CharField(
                        choices=[
                            ("account_access", "Account access or recovery"),
                            ("account_security", "Account security alert"),
                            ("external_invitation", "External invitation"),
                            ("known_user_invitation", "Known-user invitation"),
                            ("project_notification", "Project notification"),
                            ("export", "Export"),
                            ("operational", "Operational alert"),
                        ],
                        max_length=32,
                    ),
                ),
                ("template_key", models.CharField(max_length=96)),
                ("payload_ciphertext", models.TextField(blank=True)),
                ("payload_schema_version", models.PositiveSmallIntegerField(default=1)),
                ("idempotency_key", models.CharField(max_length=255, unique=True)),
                ("message_id", models.CharField(max_length=255, unique=True)),
                ("openpgp_fingerprint", models.CharField(blank=True, max_length=64)),
                ("configuration_set", models.CharField(blank=True, max_length=64)),
                ("provider_message_id", models.CharField(blank=True, db_index=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("processing", "Processing"),
                            ("suppressed_preference", "Suppressed by preference"),
                            ("suppressed_no_key", "Suppressed because no active key exists"),
                            ("suppressed_bounce", "Suppressed after hard bounce"),
                            ("suppressed_complaint", "Suppressed after complaint"),
                            ("accepted", "Accepted by transport"),
                            ("acceptance_unknown", "Transport acceptance unknown"),
                            ("delivered", "Delivered"),
                            ("failed_retryable", "Retryable failure"),
                            ("failed_permanent", "Permanent failure"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_error_code", models.CharField(blank=True, max_length=64)),
                ("last_error_detail", models.CharField(blank=True, max_length=255)),
                ("expires_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("suppressed_at", models.DateTimeField(blank=True, null=True)),
                ("terminal_at", models.DateTimeField(blank=True, db_index=True, null=True)),
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
                    "openpgp_key",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="outbox_entries",
                        to="db.useropenpgpkey",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="email_outbox_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "email_outbox", "ordering": ("created_at",)},
        ),
        migrations.CreateModel(
            name="EmailSuppression",
            fields=audit_fields()
            + [
                ("email_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("hard_bounce", "Hard bounce"),
                            ("complaint", "Complaint"),
                            ("invalid_recipient", "Invalid recipient"),
                            ("administrative", "Administrative"),
                        ],
                        max_length=32,
                    ),
                ),
                ("source", models.CharField(default="hangar", max_length=32)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("provider_event_id", models.CharField(blank=True, max_length=255)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("deactivation_reason", models.CharField(blank=True, max_length=255)),
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
                    "recipient",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="email_suppressions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "email_suppressions", "ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="EmailDeliveryEvent",
            fields=audit_fields()
            + [
                ("provider", models.CharField(default="ses", max_length=32)),
                ("provider_event_id", models.CharField(max_length=255, unique=True)),
                ("provider_message_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("event_type", models.CharField(db_index=True, max_length=32)),
                ("occurred_at", models.DateTimeField(db_index=True)),
                ("metadata", models.JSONField(default=dict)),
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
                    "outbox",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="provider_events",
                        to="db.emailoutbox",
                    ),
                ),
            ],
            options={"db_table": "email_delivery_events", "ordering": ("-occurred_at",)},
        ),
        migrations.AddField(
            model_name="emailnotificationlog",
            name="outbox",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="notification_logs",
                to="db.emailoutbox",
            ),
        ),
        migrations.AddConstraint(
            model_name="useropenpgpkey",
            constraint=models.UniqueConstraint(fields=("user", "version"), name="uniq_openpgp_user_version"),
        ),
        migrations.AddConstraint(
            model_name="useropenpgpkey",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), ("status", "active")),
                fields=("user",),
                name="uniq_active_openpgp_key_per_user",
            ),
        ),
        migrations.AddIndex(
            model_name="openpgpkeychallenge",
            index=models.Index(fields=["key", "expires_at"], name="openpgp_challenge_due_idx"),
        ),
        migrations.AddIndex(
            model_name="emailoutbox",
            index=models.Index(fields=["status", "next_attempt_at"], name="email_outbox_due_idx"),
        ),
        migrations.AddIndex(
            model_name="emailoutbox",
            index=models.Index(fields=["status", "lease_expires_at"], name="email_outbox_lease_idx"),
        ),
        migrations.AddIndex(
            model_name="emailoutbox",
            index=models.Index(fields=["recipient", "status"], name="email_outbox_recipient_idx"),
        ),
        migrations.AddConstraint(
            model_name="emailsuppression",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), ("is_active", True)),
                fields=("email_hash", "reason"),
                name="uniq_active_email_suppression",
            ),
        ),
    ]
