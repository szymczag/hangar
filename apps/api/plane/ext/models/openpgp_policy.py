# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Instance-administered control over a person's OpenPGP key.

An organisation that escrows keys needs to set the certificate its people's mail
is encrypted to, and to stop them replacing it. That is a real requirement and
also a serious power: whoever sets the key can read everything encrypted to it,
so the model records who did it and when, and the record cannot be edited
afterwards.

The lock belongs to the person rather than to a key. Attaching it to a key would
make it trivial to escape by enrolling a new one, which is the exact thing it
exists to prevent.
"""

# Django imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class UserOpenPGPPolicy(BaseModel):
    """Whether this account may manage its own encryption key."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="openpgp_policy",
    )
    is_locked = models.BooleanField(default=False)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="openpgp_policies_applied",
    )
    locked_at = models.DateTimeField(null=True, blank=True)
    # Why the administrator took over, for whoever reads this later.
    note = models.TextField(blank=True)

    class Meta:
        db_table = "ext_user_openpgp_policies"
        verbose_name = "User OpenPGP policy"

    def __str__(self):
        return f"{self.user_id} locked={self.is_locked}"


class OpenPGPAdminAction(BaseModel):
    """An append-only record of an administrator acting on someone's key.

    Setting another person's encryption key is indistinguishable, from the
    outside, from an administrator arranging to read their mail. The difference
    is that it is recorded, so this record is immutable — the same treatment
    federated identity imports get, and for the same reason.
    """

    class Action(models.TextChoices):
        KEY_SET = "key-set", "Key set by administrator"
        LOCKED = "locked", "Self-service locked"
        UNLOCKED = "unlocked", "Self-service unlocked"

    subject = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="openpgp_admin_actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="openpgp_admin_actions_performed",
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    # Identifies the certificate without storing it twice.
    primary_fingerprint = models.CharField(max_length=64, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        db_table = "ext_openpgp_admin_actions"
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("OpenPGP administrative records are immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("OpenPGP administrative records are immutable")
