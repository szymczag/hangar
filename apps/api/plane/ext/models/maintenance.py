# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The instance-wide notice an operator raises to announce downtime.

This is a model rather than another `InstanceConfiguration` row for two reasons.

The window needs real `DateTimeField`s. Stored as strings, deciding whether a
notice is active would mean comparing ISO text in the browser, in whatever
timezone the reader happens to be in. As columns, the server answers the
question once, against `timezone.now()`, and every client agrees.

And `PATCH /api/instances/configurations/` refuses every write when
`SKIP_ENV_VAR` is false, because those values are never read back when the
deployment environment is authoritative. A notice read from its own table by its
own view does not have that problem — and an operator on a config-as-code
deployment must still be able to announce an outage, which is precisely when
they would need to most.

There is deliberately no link field. A full-width strip rendered above the whole
application is a phishing surface even as plain text, and nothing in this repo
sets a CSP.
"""

# Python imports
import hashlib

# Django imports
from django.conf import settings
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class InstanceMaintenanceNotice(BaseModel):
    """The single notice shown across the instance. At most one row exists."""

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    is_enabled = models.BooleanField(default=False)
    message = models.TextField(blank=True)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    # Both optional: "we are working on it" is a legitimate notice with no window.
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    # Off by default. The read endpoint has to be anonymous for the sign-in page
    # to show anything, so publishing to people without an account is a decision
    # the operator makes rather than one the design makes for them.
    show_on_sign_in = models.BooleanField(default=False)
    updated_by_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_notices_updated",
    )

    class Meta:
        db_table = "ext_instance_maintenance_notices"
        verbose_name = "Instance maintenance notice"

    def __str__(self):
        return f"{self.severity} enabled={self.is_enabled}"

    def is_active(self, now):
        """Whether this notice should be shown at `now`.

        The window bounds are independent: a notice with only `ends_at` is
        active until then, and one with only `starts_at` is active from then on.
        """
        if not self.is_enabled or not self.message.strip():
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now >= self.ends_at:
            return False
        return True

    @property
    def fingerprint(self):
        """Identifies this wording and window, so a dismissal can key off it.

        A digest rather than a counter: toggling the same notice off and on
        again must not re-nag people who already read it, while any edit to what
        it says or when it applies brings it back for everyone.
        """
        parts = [
            self.message.strip(),
            self.severity,
            self.starts_at.isoformat() if self.starts_at else "",
            self.ends_at.isoformat() if self.ends_at else "",
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
