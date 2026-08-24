# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Security keys registered against the instance-admin console."""

# Django imports
from django.conf import settings
from django.db import models
from django.db.models import Q, UniqueConstraint

# Module imports
from plane.db.models.base import BaseModel


class InstanceAdminWebAuthnCredential(BaseModel):
    """One registered authenticator.

    Bound to the User rather than to InstanceAdmin: administrator rows are hard
    deleted when someone is demoted, and a person who is promoted again should
    not have to register their key a second time.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_webauthn_credentials",
    )
    # base64url of the raw credential id. Text rather than binary so it is
    # indexable and comparable without driver-specific handling; the spec caps
    # the raw value at 1023 bytes, which stays inside Postgres' btree limit.
    credential_id = models.CharField(max_length=1400, db_index=True)
    # base64url of the COSE public key, stored in the clear: it is a public key,
    # and plane/license/utils/encryption.py returns "" on failure, which would
    # silently brick an administrator's only credential.
    public_key = models.TextField()
    sign_count = models.PositiveBigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    aaguid = models.CharField(max_length=36, blank=True, default="")
    # 32 random bytes per administrator, reused across their credentials.
    # Deliberately not the user's UUID, which would hand a database identifier
    # to every authenticator they register.
    user_handle = models.CharField(max_length=64)
    nickname = models.CharField(max_length=64)
    # Backup eligibility says the key is synced to a cloud account, which
    # materially changes what possession of it proves. Surfaced, not enforced.
    backup_eligible = models.BooleanField(default=False)
    backup_state = models.BooleanField(default=False)
    last_uv = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_used_ip = models.CharField(max_length=45, blank=True, default="")
    # Set when a signature counter goes backwards. Kept separate from
    # deleted_at so the forensic record survives a later cleanup.
    disabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_instance_admin_webauthn_credentials"
        verbose_name = "Instance Admin WebAuthn Credential"
        ordering = ("-created_at",)
        constraints = [
            # Global, not per user: this makes "that credential belongs to a
            # different administrator" impossible at the database level rather
            # than something a view has to remember to check.
            UniqueConstraint(
                fields=("credential_id",),
                condition=Q(deleted_at__isnull=True),
                name="uniq_admin_webauthn_credential_id",
            ),
            UniqueConstraint(
                fields=("user", "nickname"),
                condition=Q(deleted_at__isnull=True),
                name="uniq_admin_webauthn_nickname_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} <{self.nickname}>"


class InstanceAdminWebAuthnChallenge(BaseModel):
    """A single-use challenge issued for one registration or assertion."""

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        AUTHENTICATION = "authentication", "Authentication"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_webauthn_challenges",
    )
    purpose = models.CharField(max_length=16, choices=Purpose.choices)
    # base64url of 32 random bytes. Stored in the clear because the client
    # echoes it back by design — unlike a bearer token, it is not a secret.
    challenge = models.CharField(max_length=128, db_index=True)
    # Binds the challenge to the session that asked for it, so a challenge
    # observed elsewhere cannot be completed from another session.
    session_key = models.CharField(max_length=128, db_index=True)
    # Snapshot of the values used to mint it, so verification uses the same
    # ones even if configuration changes mid-flight.
    rp_id = models.CharField(max_length=255)
    origin = models.CharField(max_length=255)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_instance_admin_webauthn_challenges"
        verbose_name = "Instance Admin WebAuthn Challenge"
        ordering = ("-created_at",)
        constraints = [
            UniqueConstraint(fields=("challenge",), name="uniq_admin_webauthn_challenge"),
        ]

    def __str__(self):
        return f"{self.purpose} for {self.user_id}"
