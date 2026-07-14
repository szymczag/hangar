# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from ..mixins import TimeAuditModel


def federated_binding_key(provider: str, issuer: str, subject_format: str, subject: str) -> str:
    """Return an unambiguous, fixed-size key for an external identity."""
    values = (provider, issuer, subject_format, subject)
    framed = b"".join(len(value.encode("utf-8")).to_bytes(4, "big") + value.encode("utf-8") for value in values)
    return hashlib.sha256(framed).hexdigest()


class FederatedIdentity(TimeAuditModel):
    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        OIDC = "oidc", "OpenID Connect"
        SAML = "saml", "SAML"

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.ForeignKey("db.User", on_delete=models.CASCADE, related_name="federated_identities")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    issuer = models.CharField(max_length=2048)
    subject_format = models.CharField(max_length=512, blank=True)
    subject = models.CharField(max_length=2048)
    binding_key = models.CharField(max_length=64, unique=True, editable=False)
    email_at_link = models.CharField(max_length=255, blank=True)
    last_email = models.CharField(max_length=255, blank=True)
    last_authenticated_at = models.DateTimeField(null=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "federated_identities"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["user", "provider"], name="fed_identity_user_provider_idx")]

    def save(self, *args, **kwargs):
        expected_key = federated_binding_key(self.provider, self.issuer, self.subject_format, self.subject)
        if not self._state.adding:
            stored = (
                type(self)
                .objects.filter(pk=self.pk)
                .values(
                    "user_id",
                    "provider",
                    "issuer",
                    "subject_format",
                    "subject",
                )
                .first()
            )
            presented = {
                "user_id": self.user_id,
                "provider": self.provider,
                "issuer": self.issuer,
                "subject_format": self.subject_format,
                "subject": self.subject,
            }
            if stored is None or stored != presented:
                raise ValidationError("Federated identity bindings are immutable")
        if self.binding_key and self.binding_key != expected_key:
            raise ValidationError("Federated identity binding key does not match its identity fields")
        self.binding_key = expected_key
        super().save(*args, **kwargs)


class FederatedIdentityImportAudit(TimeAuditModel):
    """Append-only record of an administrator identity-mapping import."""

    id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True, primary_key=True)
    provider = models.CharField(max_length=32, choices=FederatedIdentity.Provider.choices)
    issuer = models.CharField(max_length=2048)
    input_sha256 = models.CharField(max_length=64)
    source_name = models.CharField(max_length=512)
    row_count = models.PositiveIntegerField()
    imported_count = models.PositiveIntegerField()
    existing_count = models.PositiveIntegerField()
    report = models.JSONField(default=dict)

    class Meta:
        db_table = "federated_identity_import_audits"
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Federated identity import audit records are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Federated identity import audit records are immutable")
