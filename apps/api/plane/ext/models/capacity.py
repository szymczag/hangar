# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import hmac
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from plane.db.models.base import BaseModel


def empty_week():
    """Retained for historical migrations."""
    return {day: [] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def default_working_week():
    working_day = [{"start": "09:00", "end": "22:00"}]
    return {
        day: ([dict(working_day[0])] if day not in ("sat", "sun") else [])
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    }


class ImmutableCapacityAuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Capacity audit events are immutable.")

    def delete(self):
        raise ValidationError("Capacity audit events are immutable.")


class CapacityAuditEvent(models.Model):
    class Action(models.TextChoices):
        TRAINER_ACTIVATED = "trainer.activated", "Trainer activated"
        TRAINER_SUSPENDED = "trainer.suspended", "Trainer suspended"
        SCHEDULE_UPDATED = "schedule.updated", "Schedule updated"
        GOOGLE_CONNECTED = "google.connected", "Google connected"
        CALENDARS_UPDATED = "google.calendars_updated", "Calendars updated"
        GOOGLE_DISCONNECTED = "google.disconnected", "Google disconnected"
        WORKSHOP_UPDATED = "workshop.updated", "Workshop updated"
        WORKSHOP_REMOVED = "workshop.removed", "Workshop removed"
        PLAN_DRAFT_CREATED = "plan_draft.created", "Plan draft created"
        PLAN_DRAFT_UPDATED = "plan_draft.updated", "Plan draft updated"
        PLAN_DRAFT_REMOVED = "plan_draft.removed", "Plan draft removed"
        PLAN_HOLD_CREATED = "plan_hold.created", "Plan hold created"
        PLAN_HOLD_RELEASED = "plan_hold.released", "Plan hold released"
        PLAN_SCHEDULED = "plan.scheduled", "Plan scheduled"
        CHECKLIST_TEMPLATE_UPDATED = "checklist_template.updated", "Checklist template updated"
        CHECKLIST_TEMPLATE_REMOVED = "checklist_template.removed", "Checklist template removed"
        CHECKLIST_APPLIED = "checklist.applied", "Checklist applied"
        WORKSHOP_ROLE_UPDATED = "workshop_role.updated", "Workshop role updated"
        WORKSHOP_ROLE_REMOVED = "workshop_role.removed", "Workshop role removed"
        CALENDAR_WRITER_CONNECTED = "calendar_writer.connected", "Calendar writer connected"
        CALENDAR_WRITER_REMOVED = "calendar_writer.removed", "Calendar writer removed"
        WORKSHOPS_ENABLED = "workshops.enabled", "Workshops enabled in a project"
        WORKSHOPS_DISABLED = "workshops.disabled", "Workshops disabled in a project"

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workspace_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField(db_index=True)
    trainer_id = models.UUIDField(null=True, blank=True, db_index=True)
    issue_id = models.UUIDField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=64, choices=Action.choices)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableCapacityAuditEventQuerySet.as_manager()

    class Meta:
        db_table = "ext_capacity_audit_events"
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["workspace_id", "created_at"], name="ext_cap_audit_ws_time_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Capacity audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Capacity audit events are immutable.")


class TrainerProfile(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="trainer_profiles")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trainer_profiles")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    timezone = models.CharField(max_length=255, default="UTC")
    weekly_schedule = models.JSONField(default=default_working_week)
    schedule_revision = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ext_trainer_profiles"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=Q(deleted_at__isnull=True),
                name="ext_trainer_unique_workspace_user",
            )
        ]
        indexes = [models.Index(fields=["workspace", "status"], name="ext_trainer_ws_status_idx")]


class GoogleCalendarCredential(BaseModel):
    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        REAUTHORIZATION_REQUIRED = "reauthorization_required", "Reauthorization required"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_calendar_credentials"
    )
    google_subject = models.CharField(max_length=255)
    encrypted_refresh_token = models.TextField()
    encryption_key_id = models.CharField(max_length=64)
    granted_scopes = models.JSONField(default=list)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CONNECTED)
    last_successful_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    encrypted_google_email = models.TextField(blank=True)
    primary_calendar_timezone = models.CharField(max_length=64, blank=True)
    timezone_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_google_calendar_credentials"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "google_subject"],
                condition=Q(deleted_at__isnull=True),
                name="ext_gcal_credential_unique_subject",
            )
        ]


class TrainerCalendarSelection(BaseModel):
    trainer = models.OneToOneField(TrainerProfile, on_delete=models.CASCADE, related_name="calendar_selection")
    credential = models.ForeignKey(
        GoogleCalendarCredential, on_delete=models.CASCADE, related_name="trainer_selections"
    )
    training_events_enabled = models.BooleanField(default=False)
    encrypted_calendar_ids = models.JSONField(default=list)
    calendar_id_hashes = models.JSONField(default=list)
    revision = models.PositiveBigIntegerField(default=1)

    @staticmethod
    def calendar_hash(calendar_id: str) -> str:
        return hmac.new(settings.SECRET_KEY.encode(), calendar_id.encode(), hashlib.sha256).hexdigest()

    class Meta:
        db_table = "ext_trainer_calendar_selections"


class WorkshopSchedule(BaseModel):
    issue = models.OneToOneField("db.Issue", on_delete=models.CASCADE, related_name="workshop_schedule")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_schedules")
    project = models.ForeignKey("db.Project", on_delete=models.CASCADE, related_name="workshop_schedules")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    preparation_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_before_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_after_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )

    class Meta:
        db_table = "ext_workshop_schedules"
        indexes = [
            models.Index(fields=["workspace", "starts_at", "ends_at"], name="ext_workshop_ws_range_idx"),
            models.Index(fields=["project", "starts_at"], name="ext_workshop_proj_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="ext_workshop_valid_range")
        ]

    def save(self, *args, **kwargs):
        self.workspace_id = self.issue.workspace_id
        self.project_id = self.issue.project_id
        super().save(*args, **kwargs)


class WorkshopSession(BaseModel):
    source_plan = models.ForeignKey(
        "ext.WorkshopPlanDraft", null=True, blank=True, on_delete=models.SET_NULL, related_name="scheduled_sessions"
    )
    source_hold = models.OneToOneField(
        "ext.WorkshopPlanHold", null=True, blank=True, on_delete=models.SET_NULL, related_name="scheduled_session"
    )
    schedule = models.ForeignKey(WorkshopSchedule, on_delete=models.CASCADE, related_name="sessions")
    position = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    preparation_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_before_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_after_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    trainers = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="workshop_sessions")

    class Meta:
        db_table = "ext_workshop_sessions"
        ordering = ("position", "starts_at", "id")
        indexes = [models.Index(fields=["starts_at", "ends_at"], name="ext_workshop_session_range_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")), name="ext_workshop_session_valid_range"
            ),
            models.UniqueConstraint(fields=["schedule", "position"], name="ext_workshop_session_position"),
        ]


class WorkshopPlanDraft(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_plan_drafts")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workshop_plan_drafts")
    # What this plan is for. Nullable because a coordinator can explore before
    # there is anything to attach the answer to -- but a plan without one cannot
    # be scheduled, because there is nowhere for the sessions to land.
    issue = models.ForeignKey(
        "db.Issue",
        on_delete=models.CASCADE,
        related_name="workshop_plan_drafts",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    duration_minutes = models.PositiveIntegerField(validators=[MinValueValidator(15), MaxValueValidator(10080)])
    preparation_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_before_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    travel_after_minutes = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(1440)]
    )
    trainer_ids = models.JSONField(default=list)
    revision = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "ext_workshop_plan_drafts"
        ordering = ("-updated_at", "-created_at")
        indexes = [models.Index(fields=["workspace", "owner", "updated_at"], name="ext_plan_draft_owner_idx")]


class WorkshopPlanHold(BaseModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RELEASED = "released", "Released"
        CONFIRMED = "confirmed", "Confirmed"
        # Spent rather than let go: the block it reserved is now a real session
        # on a work item, and the audit trail should not have to guess which of
        # the two happened.
        SCHEDULED = "scheduled", "Scheduled"

    draft = models.ForeignKey(WorkshopPlanDraft, on_delete=models.CASCADE, related_name="holds")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_plan_holds")
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workshop_plan_holds")
    workshop_starts_at = models.DateTimeField()
    workshop_ends_at = models.DateTimeField()
    blocked_starts_at = models.DateTimeField()
    blocked_ends_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        db_table = "ext_workshop_plan_holds"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "trainer", "status", "expires_at"], name="ext_plan_hold_lookup_idx"),
            models.Index(fields=["draft", "status"], name="ext_plan_hold_draft_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(workshop_ends_at__gt=models.F("workshop_starts_at")),
                name="ext_plan_hold_workshop_range",
            ),
            models.CheckConstraint(
                condition=Q(blocked_ends_at__gt=models.F("blocked_starts_at")),
                name="ext_plan_hold_blocked_range",
            ),
        ]


class WorkshopBookingOperation(BaseModel):
    draft = models.ForeignKey(WorkshopPlanDraft, on_delete=models.CASCADE, related_name="booking_operations")
    key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    result = models.JSONField()

    class Meta:
        db_table = "ext_workshop_booking_operations"
        constraints = [models.UniqueConstraint(fields=["draft", "key"], name="ext_booking_draft_key")]


class GoogleTrainingRule(BaseModel):
    """A calendar whose events are this workspace's trainings.

    The calendar is the whole rule. An organizer address used to be half of it,
    and could not work: a shared calendar that hides its guest list returns no
    attendees to the API, so there was nothing to test an organizer against, and
    Google names the calendar itself as the organizer of anything created on it
    rather than the person who created it.

    `encrypted_organizer` is retained, unused and written empty, so that a
    downgrade to a release that still reads it finds a column rather than an
    error. It goes in a later migration, once no supported release reads it.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="google_training_rules")
    label = models.CharField(max_length=100)
    encrypted_calendar_id = models.TextField()
    encrypted_organizer = models.TextField(blank=True, default="")
    encryption_key_id = models.CharField(max_length=64)
    # Whose Google account writes workshops into this calendar.
    #
    # A person's own connection rather than a service account, deliberately: the
    # coordinator already makes this move by hand, so the trail Google keeps
    # names somebody who can be asked about it, and the organization never has
    # to grant a standing credential write access to a shared calendar.
    #
    # The cost is accepted rather than hidden -- write-back depends on one
    # person's token staying healthy, and every caller must treat "no writer" as
    # an ordinary state instead of an error, because planning has to keep
    # working while somebody reconnects.
    #
    # SET_NULL, not CASCADE: losing the credential must leave the rule and its
    # recognition intact. Reading a calendar never needed a writer.
    writer_credential = models.ForeignKey(
        "ext.GoogleCalendarCredential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="written_training_rules",
    )

    class Meta:
        db_table = "ext_google_training_rules"


class GoogleTrainingEventLink(BaseModel):
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE)
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_key = models.CharField(max_length=64)
    session = models.ForeignKey(WorkshopSession, on_delete=models.CASCADE, related_name="google_event_links")

    class Meta:
        db_table = "ext_google_training_event_links"
        constraints = [
            models.UniqueConstraint(fields=["workspace", "trainer", "event_key"], name="ext_training_event_link_unique")
        ]


class WorkshopSessionCalendarEvent(BaseModel):
    """The event a session ought to have in the shared calendar, and its progress.

    An outbox rather than a call from the request. Planning a workshop must
    succeed whether or not Google is reachable -- a coordinator who cannot book
    because a calendar API is slow would rightly stop using the planner -- so
    the request records the intent in the same transaction as the session and a
    worker reconciles it afterwards.

    One row per (session, trainer): a session can be delivered by more than one
    person, and each of them gets their own invitation.
    """

    class Intent(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"

    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        SYNCED = "synced", "Synced"
        FAILED = "failed", "Failed"
        BLOCKED_NO_WRITER = "blocked_no_writer", "Blocked: no writing account"
        BLOCKED = "blocked", "Blocked"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE)
    # SET_NULL, and `source_session_id` is the durable key.
    #
    # Sessions are hard-deleted when a schedule is replaced, and deleting the
    # work item cascades into them. CASCADE here would take the row with them --
    # including the rows that still owe Google a deletion, which is precisely
    # when the row matters most.
    session = models.ForeignKey(WorkshopSession, on_delete=models.SET_NULL, null=True, blank=True)
    source_session_id = models.UUIDField(db_index=True)
    source_issue_id = models.UUIDField(null=True, blank=True, db_index=True)
    trainer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rule = models.ForeignKey("ext.GoogleTrainingRule", on_delete=models.SET_NULL, null=True, blank=True)
    # Who planned it. The worker has no request, and the audit model requires an
    # actor, so the person who caused the write is carried here rather than the
    # event being attributed to nobody.
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    credential = models.ForeignKey(
        "ext.GoogleCalendarCredential", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # The identity of the account that was meant to write, pinned at the moment
    # of planning. Checked again before writing: a rule whose writer changed in
    # between must not have a queued row silently written by somebody else.
    credential_subject = models.CharField(max_length=255, blank=True, default="")
    google_event_id = models.CharField(max_length=128, blank=True, default="")
    google_ical_uid = models.CharField(max_length=255, blank=True, default="")
    intent = models.CharField(max_length=16, choices=Intent.choices, default=Intent.PRESENT)
    desired_starts_at = models.DateTimeField(null=True, blank=True)
    desired_ends_at = models.DateTimeField(null=True, blank=True)
    desired_fingerprint = models.CharField(max_length=64, blank=True, default="")
    # `revision` moves whenever the desired state changes; `synced_revision`
    # records what Google was last told. Anything where they differ owes work,
    # whatever its state says -- which is what makes a stuck row recoverable
    # without anybody having to reason about how it got stuck.
    revision = models.PositiveBigIntegerField(default=1)
    synced_revision = models.PositiveBigIntegerField(default=0)
    state = models.CharField(max_length=24, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True, default="")
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_workshop_session_calendar_events"
        constraints = [
            models.UniqueConstraint(fields=["trainer", "source_session_id"], name="ext_workshop_calendar_event_unique"),
            models.CheckConstraint(check=Q(attempts__lte=100), name="ext_workshop_calendar_event_attempts"),
            models.CheckConstraint(
                check=Q(intent="absent") | Q(desired_starts_at__isnull=False, desired_ends_at__isnull=False),
                name="ext_workshop_calendar_event_window",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "available_at"]),
            models.Index(fields=["workspace", "state"]),
        ]


class TrainingEventOccurrence(BaseModel):
    """A recognized training invitation, kept so a report need not ask Google.

    The live paths read Google every time, which is right for them: the ledger
    shows this week and booking must not act on a quarter-hour-old answer. A
    report over a month cannot work that way -- twenty-five trainers times a
    month is a request Google will not serve in one window, and `list_events`
    refuses past two thousand events anyway.

    So a sweep writes what it recognizes here and the report reads only this
    table. The two never appear in one response, which is what keeps them from
    double counting. `event_key` is the same HMAC the live path derives, so
    `GoogleTrainingEventLink` joins on it with no new column.
    """

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        PENDING = "pending", "Pending"

    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        # Google says the invitation is gone or was declined.
        CANCELLED = "cancelled", "Cancelled"
        # A full rescan of the window did not see it. Only a full scan may
        # conclude this: an invitation moved outside the window fails the time
        # filter, so the incremental pass never sees it and must not guess.
        DISAPPEARED = "disappeared", "Disappeared"

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="training_event_occurrences")
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="training_event_occurrences"
    )
    trainer_profile = models.ForeignKey(
        TrainerProfile, on_delete=models.CASCADE, related_name="training_event_occurrences"
    )
    event_key = models.CharField(max_length=64)
    rule = models.ForeignKey(
        GoogleTrainingRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="occurrences"
    )
    # Snapshot, because a report about last quarter should still say which
    # calendar an occurrence came from after the rule itself has been removed.
    rule_label = models.CharField(max_length=100, blank=True)
    calendar_id_hash = models.CharField(max_length=64)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices)
    state = models.CharField(max_length=16, choices=State.choices, default=State.ACTIVE)
    # Encrypted at rest like every other calendar-derived value here, and only
    # ever written for events that matched a rule.
    encrypted_summary = models.TextField(blank=True)
    encryption_key_id = models.CharField(max_length=64, blank=True)
    # What this training became in Hangar, if anybody imported it.
    #
    # Not derivable from `GoogleTrainingEventLink`, which is what the import
    # creates: that link is member-level self-service to delete, so using its
    # absence as "not imported yet" lets one unlink turn a single training into
    # two Workshops. This records the decision itself, which nothing but another
    # import changes. SET_NULL because deleting the work item should leave the
    # occurrence importable again rather than deleting the calendar's record.
    imported_issue = models.ForeignKey(
        "db.Issue",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="imported_training_occurrences",
    )
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()

    class Meta:
        db_table = "ext_training_event_occurrences"
        verbose_name = "Training event occurrence"
        ordering = ("starts_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "trainer", "event_key"], name="ext_training_occurrence_unique"
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")), name="ext_training_occurrence_range"
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "starts_at", "ends_at"], name="ext_train_occ_ws_range_idx"),
            models.Index(fields=["trainer", "starts_at"], name="ext_train_occ_trainer_idx"),
            models.Index(fields=["workspace", "state", "starts_at"], name="ext_train_occ_state_idx"),
        ]

    def __str__(self):
        return f"{self.trainer_id} {self.event_key[:12]}"


class TrainingCalendarSyncState(BaseModel):
    """How far the sweep has got on one rule's calendar.

    Keyed on the rule rather than the trainer on purpose. A rule names a shared
    calendar, so every consenting trainer would read an identical event list from
    it; sweeping per trainer would multiply the quota by the roster for no extra
    information, and a wide window per trainer walks straight into the
    two-thousand-event ceiling. One read per calendar, fanned out in memory
    against each consenting trainer's own address, keeps the consent boundary
    while paying for the transport once.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="training_sync_states")
    rule = models.OneToOneField(GoogleTrainingRule, on_delete=models.CASCADE, related_name="sync_state")
    window_starts_at = models.DateTimeField()
    window_ends_at = models.DateTimeField()
    last_incremental_at = models.DateTimeField(null=True, blank=True)
    last_full_scan_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)
    failure_count = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_training_calendar_sync_states"
        verbose_name = "Training calendar sync state"
        indexes = [models.Index(fields=["available_at"], name="ext_train_sync_ready_idx")]

    def __str__(self):
        return f"{self.rule_id}"


class TrainerTrainingSyncState(BaseModel):
    """Whether a trainer's rows in the report can be trusted.

    A trainer who never consented, or who has personally lost access to the
    shared calendar, has no occurrences -- and a report must not render that as
    a trainer who simply ran no training. This is what lets the report exclude
    them from totals and say so instead.
    """

    class ConsentState(models.TextChoices):
        OK = "ok", "Ok"
        CONSENT_MISSING = "consent_missing", "Consent missing"
        REAUTH_REQUIRED = "reauth_required", "Reauthorization required"
        NOT_CONNECTED = "not_connected", "Not connected"
        ACCESS_LOST = "access_lost", "Access lost"

    trainer_profile = models.OneToOneField(TrainerProfile, on_delete=models.CASCADE, related_name="training_sync_state")
    consent_state = models.CharField(max_length=32, choices=ConsentState.choices, default=ConsentState.NOT_CONNECTED)
    last_materialized_at = models.DateTimeField(null=True, blank=True)
    last_probed_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "ext_trainer_training_sync_states"
        verbose_name = "Trainer training sync state"

    def __str__(self):
        return f"{self.trainer_profile_id} {self.consent_state}"
