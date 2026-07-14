# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Durable state for policy-aware outbound email."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from plane.mailer.enums import DeliveryMode, MailPolicyClass, OpenPGPKeyStatus, OutboxStatus, SuppressionReason

from .base import BaseModel


class UserOpenPGPKey(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="openpgp_keys",
    )
    version = models.PositiveIntegerField()
    certificate = models.TextField()
    primary_fingerprint = models.CharField(max_length=64, db_index=True)
    encryption_subkey_fingerprint = models.CharField(max_length=64)
    primary_algorithm = models.CharField(max_length=64)
    encryption_algorithm = models.CharField(max_length=64)
    encryption_key_size = models.PositiveIntegerField(null=True, blank=True)
    key_created_at = models.DateTimeField(null=True, blank=True)
    key_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    replaced_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=OpenPGPKeyStatus.choices,
        default=OpenPGPKeyStatus.PENDING,
        db_index=True,
    )

    class Meta:
        db_table = "user_openpgp_keys"
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=("user", "version"), name="uniq_openpgp_user_version"),
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(status=OpenPGPKeyStatus.ACTIVE, deleted_at__isnull=True),
                name="uniq_active_openpgp_key_per_user",
            ),
            models.UniqueConstraint(
                fields=("user",),
                condition=Q(status=OpenPGPKeyStatus.PENDING, deleted_at__isnull=True),
                name="uniq_pending_openpgp_key_per_user",
            ),
        ]


class OpenPGPKeyChallenge(BaseModel):
    key = models.ForeignKey(UserOpenPGPKey, on_delete=models.CASCADE, related_name="challenges")
    token_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "openpgp_key_challenges"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("key", "expires_at"), name="openpgp_challenge_due_idx")]


class EmailOutbox(BaseModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="email_outbox_entries",
        null=True,
        blank=True,
    )
    recipient_email = models.EmailField(max_length=320, db_index=True)
    policy_class = models.CharField(max_length=32, choices=MailPolicyClass.choices)
    template_key = models.CharField(max_length=96)
    audit_label = models.CharField(max_length=96)
    sender = models.CharField(max_length=320)
    delivery_mode = models.CharField(max_length=16, choices=DeliveryMode.choices)
    encrypted_message = models.BinaryField(blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True)
    message_id = models.CharField(max_length=255, unique=True)
    receipt_code = models.CharField(max_length=24, unique=True)
    openpgp_key = models.ForeignKey(
        UserOpenPGPKey,
        on_delete=models.SET_NULL,
        related_name="outbox_entries",
        null=True,
        blank=True,
    )
    openpgp_fingerprint = models.CharField(max_length=64, blank=True)
    configuration_set = models.CharField(max_length=64, blank=True)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=OutboxStatus.choices,
        default=OutboxStatus.QUEUED,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    last_error_detail = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    terminal_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "email_outbox"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("status", "next_attempt_at"), name="email_outbox_due_idx"),
            models.Index(fields=("status", "lease_expires_at"), name="email_outbox_lease_idx"),
            models.Index(fields=("recipient", "status"), name="email_outbox_recipient_idx"),
        ]


class EmailSuppression(BaseModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="email_suppressions",
        null=True,
        blank=True,
    )
    email_address = models.EmailField(max_length=320, db_index=True)
    reason = models.CharField(max_length=32, choices=SuppressionReason.choices)
    source = models.CharField(max_length=32, default="hangar")
    is_active = models.BooleanField(default=True, db_index=True)
    provider_event_id = models.CharField(max_length=255, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "email_suppressions"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("email_address", "reason"),
                condition=Q(is_active=True, deleted_at__isnull=True),
                name="uniq_active_email_suppression",
            )
        ]


class EmailDeliveryEvent(BaseModel):
    outbox = models.ForeignKey(
        EmailOutbox,
        on_delete=models.SET_NULL,
        related_name="provider_events",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=32, default="ses")
    provider_event_id = models.CharField(max_length=255, unique=True)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    event_type = models.CharField(max_length=32, db_index=True)
    occurred_at = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "email_delivery_events"
        ordering = ("-occurred_at",)
