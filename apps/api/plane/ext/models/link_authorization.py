# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Permission for one existing account to be linked to a provider identity.

Sign-in matches an account by binding key — a hash over provider, issuer,
subject format and subject — and the email address is not part of it. So an
account that predates SSO cannot be found by a provider assertion, and the
holder is refused with SSO_ACCOUNT_LINK_REQUIRED at every attempt.

The supported repair is an import of each person's provider subject, which for
Google means exporting the `sub` claim from the Admin SDK. That is a real
obstacle for an operator who has a list of email addresses and nothing else.

An authorization here says: the next time this address arrives from this issuer,
bind whatever subject it asserts. It is a deliberate, recorded relaxation of the
rule that an address never links an account — narrow enough to be defensible
only because of what the sign-in path checks alongside it, and it is those
conditions, not this row, that carry the security.
"""

# Django imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# Module imports
from plane.db.models.base import BaseModel


class FederatedLinkAuthorization(BaseModel):
    """One address, one issuer, one use."""

    email = models.CharField(max_length=255, db_index=True)
    provider = models.CharField(max_length=32)
    issuer = models.CharField(max_length=2048)
    # Not a foreign key to User: an address may be authorised before anyone
    # checks whether the account exists, and the account it names must not
    # disappear from the record if it is later deleted.
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="federated_link_authorizations",
    )
    note = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    # What the provider actually asserted, recorded when it is spent.
    consumed_subject = models.CharField(max_length=2048, blank=True)
    consumed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="federated_links_consumed",
    )

    class Meta:
        db_table = "ext_federated_link_authorizations"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["email", "provider"], name="fed_link_email_provider_idx")]

    @property
    def is_spendable(self) -> bool:
        return self.consumed_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.email} via {self.provider}"


class FederatedLinkAudit(BaseModel):
    """An append-only record of an account being linked by authorization.

    Linking an existing account to an identity is indistinguishable, from the
    outside, from an account takeover that happened to be authorised. The
    difference is that this exists, so it cannot be edited or removed.
    """

    email = models.CharField(max_length=255, db_index=True)
    provider = models.CharField(max_length=32)
    issuer = models.CharField(max_length=2048)
    subject = models.CharField(max_length=2048)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="federated_link_audits",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="federated_link_audits_authorized",
    )
    authorized_at = models.DateTimeField(null=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "ext_federated_link_audits"
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Federated link records are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Federated link records are immutable")
