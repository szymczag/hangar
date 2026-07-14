# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Shared enums for the outbound email subsystem."""

from django.db import models


class MailPolicyClass(models.TextChoices):
    ACCOUNT_ACCESS = "account_access", "Account access or recovery"
    ACCOUNT_SECURITY = "account_security", "Account security alert"
    EXTERNAL_INVITATION = "external_invitation", "External invitation"
    KNOWN_USER_INVITATION = "known_user_invitation", "Known-user invitation"
    PROJECT_NOTIFICATION = "project_notification", "Project notification"
    EXPORT = "export", "Export"
    OPERATIONAL = "operational", "Operational alert"


class MailDecision(models.TextChoices):
    CLEAR = "clear", "Send cleartext"
    ENCRYPT = "encrypt", "Encrypt"
    SUPPRESS = "suppress", "Suppress"


class DeliveryMode(models.TextChoices):
    CLEAR = "clear", "Cleartext account email"
    OPENPGP = "openpgp", "OpenPGP encrypted"
    SUPPRESSED = "suppressed", "Not sent"


class OutboxStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    SUPPRESSED_PREFERENCE = "suppressed_preference", "Suppressed by preference"
    SUPPRESSED_NO_KEY = "suppressed_no_key", "Suppressed because no active key exists"
    SUPPRESSED_BOUNCE = "suppressed_bounce", "Suppressed after hard bounce"
    SUPPRESSED_COMPLAINT = "suppressed_complaint", "Suppressed after complaint"
    ACCEPTED = "accepted", "Accepted by transport"
    ACCEPTANCE_UNKNOWN = "acceptance_unknown", "Transport acceptance unknown"
    DELIVERED = "delivered", "Delivered"
    FAILED_RETRYABLE = "failed_retryable", "Retryable failure"
    FAILED_PERMANENT = "failed_permanent", "Permanent failure"


class OpenPGPKeyStatus(models.TextChoices):
    PENDING = "pending", "Pending verification"
    ACTIVE = "active", "Active"
    REPLACED = "replaced", "Replaced"
    REVOKED = "revoked", "Revoked"
    EXPIRED = "expired", "Expired"
    INVALID = "invalid", "Invalid"


class SuppressionReason(models.TextChoices):
    HARD_BOUNCE = "hard_bounce", "Hard bounce"
    COMPLAINT = "complaint", "Complaint"
    INVALID_RECIPIENT = "invalid_recipient", "Invalid recipient"
    ADMINISTRATIVE = "administrative", "Administrative"
