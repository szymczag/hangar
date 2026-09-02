# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The background copy of a project's work items.

Duplicating a project's *configuration* happens inside one transaction that
holds a lock on the workspace row, which is why it is capped: crossing the cap
is the signal to build this path rather than to raise the number. Work items are
unbounded, so they are copied here instead, after that transaction has
committed and the lock is gone.

This is a much smaller thing than `ImportJob`, and deliberately so. An import
ingests a file somebody uploaded, into a project that already has contents and
other writers; it needs admission budgets, source digests and drift checks. A
copy reads rows the caller was already authorised to read and writes them into a
project created seconds earlier that nothing else writes to. What is left after
removing what does not apply is: where we got to, what we have created so far,
and who is allowed to carry on.

Resuming needs to know which source work item became which copy, and that map
is not stored: a copy keeps the source's ``sequence_id`` verbatim, so
``(project, sequence_id)`` *is* the key, derivable from two queries. That also
means every phase can skip what it already created, which is what makes a
resumed copy exact rather than approximate.

What does have to be persisted is ``remap`` -- the state, label, cycle, module
and estimate-point translation built during the synchronous configuration copy.
It lives only in ``_Remap``'s memory inside that transaction, and the job runs
long after the request is gone.
"""

# Django imports
from django.conf import settings
from django.db import models

# Module imports
from plane.db.models.base import BaseModel

# Statuses a job may still be working from. The duplicate endpoint refuses a
# second copy in a workspace that already has one of these outstanding, which is
# the real defence against somebody queueing ten large copies at once.
ACTIVE_STATUSES = ("queued", "processing")


class ProjectCopyJob(BaseModel):
    """One project's work items being copied into a freshly created project."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        COMPLETED_WITH_ERRORS = "completed_with_errors", "Completed with errors"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    class Stage(models.TextChoices):
        """Which pass the job is in, so a resume re-enters the right one."""

        ISSUES = "issues", "Work items"
        PARENTS = "parents", "Sub-item links"
        SATELLITES = "satellites", "Labels, assignees and membership"
        PROPERTIES = "properties", "Custom property values"
        RELATIONS = "relations", "Relations"
        ASSETS = "assets", "Description images"

    TERMINAL_STATUSES = (
        Status.COMPLETED,
        Status.COMPLETED_WITH_ERRORS,
        Status.FAILED,
        Status.CANCELLED,
    )

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="project_copy_jobs",
    )
    # The source may be deleted while a copy of it is still running; that is not
    # a reason to lose the record of what was copied.
    source_project = models.ForeignKey(
        "db.Project",
        on_delete=models.SET_NULL,
        null=True,
        related_name="copy_jobs_as_source",
    )
    # OneToOne rather than a foreign key with a partial unique: the target is
    # created for this job and nothing else ever writes to it, so "one job per
    # copy" is true by construction rather than by constraint. It also makes the
    # status route unambiguous -- the client polls the project it is looking at.
    target_project = models.OneToOneField(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="copy_job",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="project_copy_jobs",
    )

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    stage = models.CharField(max_length=32, choices=Stage.choices, default=Stage.ISSUES)

    # What the caller asked to copy. The job runs after the request is gone, and
    # a retry has to copy exactly what was agreed rather than today's defaults.
    plan = models.JSONField(default=dict)
    # State, label, cycle, module and estimate-point translation from the
    # synchronous configuration copy. Without this the job can map nothing.
    # Bounded by the configuration caps the synchronous path already enforces.
    remap = models.JSONField(default=dict)

    # Fixed at admission so the denominator the interface shows never moves.
    total = models.PositiveIntegerField(default=0)
    copied = models.PositiveIntegerField(default=0)
    # What was deliberately left behind, mirroring CopyResult.skipped, and the
    # per-model tallies including how many assignees were dropped.
    counts = models.JSONField(default=dict)
    skipped = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    reason = models.CharField(max_length=64, blank=True)

    # High-water mark within the current stage, in the source's `sequence_id`
    # ordering. Committed in the same transaction as the rows it accounts for,
    # so it can never claim more than was written.
    cursor = models.BigIntegerField(default=0)

    celery_task_id = models.CharField(max_length=255, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    # The lease token alone fences a stalled worker: every write re-asserts it,
    # so a zombie that wakes up holding a retired token writes nothing. The
    # import job carries a generation counter as well, because an import can be
    # cancelled mid-flight and produce competing generations; a copy cannot.
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "ext_project_copy_jobs"
        verbose_name = "Project copy job"
        ordering = ("-created_at",)
        constraints = [
            # A job that claims to be running must hold a lease and know when it
            # started; one that has finished must have let the lease go.
            models.CheckConstraint(
                check=~models.Q(status="processing") | models.Q(lease_token__isnull=False, started_at__isnull=False),
                name="ext_project_copy_job_processing_holds_lease",
            ),
            models.CheckConstraint(
                check=~models.Q(status__in=("completed", "completed_with_errors", "failed", "cancelled"))
                | models.Q(completed_at__isnull=False, lease_token__isnull=True),
                name="ext_project_copy_job_terminal_released",
            ),
        ]
        # The per-workspace concurrency guard scans for active jobs; the target
        # already has a unique index by virtue of being a OneToOne.
        indexes = [models.Index(fields=["workspace", "status"])]

    def __str__(self):
        return f"{self.target_project_id} {self.status}"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL_STATUSES
