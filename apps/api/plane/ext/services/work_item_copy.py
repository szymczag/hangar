# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Copy a project's work items into a project that was just duplicated.

Configuration is copied synchronously by :mod:`plane.ext.services.project_copy`,
inside one transaction that holds a lock on the workspace row. Work items are
unbounded, so they are copied here instead -- after that transaction has
committed, by a background job, with the lock long gone.

Four things about this are load-bearing and quiet if broken:

* ``bulk_create`` bypasses ``save()``. Every field ``Issue.save()`` would have
  derived -- ``workspace``, ``sequence_id``, ``sort_order``,
  ``description_stripped`` -- is set explicitly here, and ``created_at`` needs a
  second pass because ``auto_now_add`` overwrites whatever insert supplies.
* A copy keeps the source's ``sequence_id``. That is what makes
  ``(project, sequence_id)`` a durable source-to-copy key, so a resumed job can
  rebuild its translation from two queries and skip what it already wrote. It is
  also why the synchronous path reserves the range first: nothing enforces
  uniqueness on ``(project, sequence)``, so an item somebody creates in the copy
  while this runs would otherwise silently take a number the copy still owes.
* Parents are linked in a second pass. Sub-items nest arbitrarily deep, and a
  flat remap after the fact needs no traversal and no ordering guarantee.
* Every phase is idempotent by skipping the ``sequence_id`` values already
  present in the target. A job that dies mid-batch and is redispatched must add
  what is missing, never a second copy of what is not.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.html import strip_tags

from plane.db.models import (
    CycleIssue,
    Issue,
    IssueAssignee,
    IssueLabel,
    IssueLink,
    IssueRelation,
    IssueSequence,
    ModuleIssue,
    ProjectMember,
)
from plane.ext.models import IssuePropertyValue

# Big enough that the per-batch overhead is amortised, small enough that a
# killed worker loses little and a transaction stays short.
BATCH_SIZE = 500


class StoredRemap:
    """The configuration translation, read back from the job row.

    ``_Remap`` in the synchronous service lives only in memory inside the
    transaction that builds it. The job runs long after that, so the mapping is
    persisted as ``{namespace: {old_id: new_id}}`` and read back through this,
    which keeps the same call shape rather than inviting ``dict.get(a, b)`` to
    be read as a lookup with a default.
    """

    def __init__(self, entries: dict | None):
        self._entries = entries or {}

    def get(self, label: str, old_id):
        if old_id is None:
            return None
        return self._entries.get(label, {}).get(str(old_id))

    def has(self, label: str) -> bool:
        return bool(self._entries.get(label))


@dataclass
class CopyTally:
    """What the job created, and what it deliberately did not."""

    counts: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)

    def add(self, label: str, count: int) -> None:
        if count:
            self.counts[label] = self.counts.get(label, 0) + count

    def note(self, reason: str) -> None:
        if reason not in self.skipped:
            self.skipped.append(reason)


def source_work_items(source_project_id):
    """The work items a copy should carry, in a stable order.

    ``Issue.objects`` is the soft-delete manager, not the filtering one:
    ``Issue.issue_objects`` additionally excludes triage, archived and
    archived-project items, which a copy *should* reproduce. Only drafts are
    excluded here, because a draft is one author's unsaved composition that
    nobody else can see.

    Ordering by ``sequence_id`` is what makes the cursor meaningful, and it is
    the same key the copy is written under.
    """
    return Issue.objects.filter(project_id=source_project_id, is_draft=False).order_by("sequence_id")


def existing_sequence_ids(target_project_id) -> set:
    """Work item numbers already present in the copy.

    This is the whole of the resume mechanism: whatever is here was written by
    an earlier attempt, and must not be written again.
    """
    return set(Issue.objects.filter(project_id=target_project_id).values_list("sequence_id", flat=True))


def translation(source_project_id, target_project_id) -> dict:
    """Source work item id -> copied work item id.

    Derived rather than stored, because the copy shares the source's numbering.
    Two queries and a dict join replace a map that would otherwise have to be
    persisted, kept in step with the rows, and capped for size.
    """
    source = dict(Issue.objects.filter(project_id=source_project_id, is_draft=False).values_list("sequence_id", "id"))
    target = dict(Issue.objects.filter(project_id=target_project_id).values_list("sequence_id", "id"))
    return {source_id: target[sequence_id] for sequence_id, source_id in source.items() if sequence_id in target}


def reserve_sequence_range(target_project, source_project_id) -> int:
    """Push the target's next work item number past the whole copied range.

    One row, ``issue=NULL`` and ``deleted=True`` -- which is what
    ``IssueSequence.issue`` being nullable is for. ``Issue.save()`` derives the
    next number from ``Max(sequence)``, so this makes an item created in the copy
    while the job runs land above everything the copy still owes.

    Without it the collision is silent: two items numbered alike, and no
    constraint to raise.
    """
    highest = (
        (IssueSequence.objects.filter(project_id=source_project_id).aggregate(largest=Max("sequence"))["largest"]) or 0
    )
    if highest:
        IssueSequence.objects.create(
            issue=None,
            sequence=highest,
            deleted=True,
            project=target_project,
            workspace_id=target_project.workspace_id,
        )
    return highest


def copy_issue_batch(*, sources, target_project, remap, type_ids) -> list:
    """Insert one batch of work items and everything ``save()`` would have set.

    Returns the created rows, so the caller can key its satellite passes off
    them. ``ignore_conflicts`` is deliberately not used: on PostgreSQL it makes
    the returned primary keys unreliable, and they are load-bearing here.
    """
    default_type_id = type_ids.get("default")
    rows = []
    for source in sources:
        # A type that is not available in the copy would be a dangling
        # reference. `_copy_work_item_types` re-links every source type, so this
        # only bites on drift.
        type_id = source.type_id if source.type_id in type_ids["available"] else default_type_id
        rows.append(
            Issue(
                project=target_project,
                workspace_id=target_project.workspace_id,
                # Verbatim: this is the source-to-copy key.
                sequence_id=source.sequence_id,
                # Verbatim: somebody's manual ordering is content, not an index.
                sort_order=source.sort_order,
                name=source.name,
                description_html=source.description_html,
                description_json=source.description_json,
                description_binary=source.description_binary,
                # `save()` would have derived this; `bulk_create` will not.
                description_stripped=(None if not source.description_html else strip_tags(source.description_html)),
                priority=source.priority,
                point=source.point,
                start_date=source.start_date,
                target_date=source.target_date,
                completed_at=source.completed_at,
                archived_at=source.archived_at,
                is_draft=False,
                state_id=remap.get("state", source.state_id),
                estimate_point_id=remap.get("estimate_point", source.estimate_point_id),
                type_id=type_id,
                # Linked in a second pass once every row exists.
                parent=None,
                # Cleared, or a later Todoist re-import believes it already
                # created rows it did not: `todoist_issue_external_uidx` is a
                # partial unique on (project, external_source, external_id).
                external_source=None,
                external_id=None,
                created_by_id=source.created_by_id,
            )
        )

    created = Issue.objects.bulk_create(rows, batch_size=BATCH_SIZE)

    IssueSequence.objects.bulk_create(
        [
            IssueSequence(
                issue=row,
                sequence=row.sequence_id,
                project=target_project,
                workspace_id=target_project.workspace_id,
            )
            for row in created
        ],
        batch_size=BATCH_SIZE,
    )

    # `created_at` is auto_now_add and `updated_at` is auto_now, so both were
    # overwritten on insert. `bulk_update` calls pre_save(add=False), under
    # which neither re-applies -- this pass is the only thing that makes
    # "preserve the original dates" true. Restoring only `created_at` would
    # leave every copy reading "created two years ago, updated just now".
    for source, row in zip(sources, created):
        row.created_at = source.created_at
        row.updated_at = source.updated_at
    Issue.objects.bulk_update(created, ["created_at", "updated_at"], batch_size=BATCH_SIZE)

    return created


def link_parents(*, source_project_id, target_project, tally: CopyTally) -> None:
    """Second pass: rebuild the sub-item tree.

    Every work item was inserted with no parent, so this is a flat remap rather
    than a traversal -- arbitrary nesting depth and any insertion order both
    fall out for free. A parent that was not copied (a draft, or an item in
    another project) leaves the child at the top level, which is the only honest
    answer: the alternative is a foreign key pointing into the source project.
    """
    ids = translation(source_project_id, target_project.id)
    if not ids:
        return

    parented = source_work_items(source_project_id).exclude(parent_id=None).values_list("id", "parent_id")

    rows, dropped = [], 0
    for source_id, source_parent_id in parented:
        target_id = ids.get(source_id)
        if target_id is None:
            continue
        target_parent_id = ids.get(source_parent_id)
        if target_parent_id is None:
            dropped += 1
            continue
        rows.append(Issue(id=target_id, parent_id=target_parent_id))

    if rows:
        Issue.objects.bulk_update(rows, ["parent"], batch_size=BATCH_SIZE)
    tally.add("sub_items", len(rows))
    if dropped:
        tally.add("parents_dropped", dropped)
        tally.note("work_items:parent-dropped")


def copy_satellites(*, source_project_id, target_project, ids, remap: StoredRemap, plan, tally: CopyTally) -> None:
    """Labels, assignees, links, and cycle and module membership.

    Each is skipped, with a note, when the thing it points at was not itself
    copied. Forcing cycles on because work items were asked for would copy other
    people's sprint planning without anybody requesting it.
    """
    source_ids = list(ids)
    if not source_ids:
        return

    stamp = {"project": target_project, "workspace_id": target_project.workspace_id}

    # Labels
    if plan.get("labels"):
        rows, seen = [], set()
        for issue_id, label_id in IssueLabel.objects.filter(issue_id__in=source_ids).values_list(
            "issue_id", "label_id"
        ):
            new_label_id = remap.get("label", label_id)
            key = (ids[issue_id], new_label_id)
            # The source can hold duplicates: IssueLabel has no unique
            # constraint at all, so nothing there stopped them being created.
            if new_label_id is None or key in seen:
                continue
            seen.add(key)
            rows.append(IssueLabel(issue_id=ids[issue_id], label_id=new_label_id, **stamp))
        IssueLabel.objects.bulk_create(rows, batch_size=BATCH_SIZE)
        tally.add("labels", len(rows))
    else:
        tally.note("work_items:labels-not-copied")

    # Assignees, kept only where the person is in the copy.
    members = set(
        ProjectMember.objects.filter(project=target_project, is_active=True).values_list("member_id", flat=True)
    )
    rows, dropped = [], 0
    for issue_id, assignee_id in IssueAssignee.objects.filter(issue_id__in=source_ids).values_list(
        "issue_id", "assignee_id"
    ):
        if assignee_id not in members:
            dropped += 1
            continue
        rows.append(IssueAssignee(issue_id=ids[issue_id], assignee_id=assignee_id, **stamp))
    IssueAssignee.objects.bulk_create(rows, batch_size=BATCH_SIZE)
    tally.add("assignees", len(rows))
    if dropped:
        tally.add("assignees_dropped", dropped)
        tally.note("work_items:assignees-not-in-copy")

    # Links
    rows, seen = [], set()
    for link in IssueLink.objects.filter(issue_id__in=source_ids):
        key = (ids[link.issue_id], link.url)
        # Uniqueness of (url, issue) is a serializer rule, not a constraint, so
        # the source may already carry duplicates.
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            IssueLink(issue_id=ids[link.issue_id], title=link.title, url=link.url, metadata=link.metadata, **stamp)
        )
    IssueLink.objects.bulk_create(rows, batch_size=BATCH_SIZE)
    tally.add("links", len(rows))

    # Cycle and module membership, only where the cycle or module came across.
    for enabled, model, field_name, namespace, label in (
        (plan.get("cycles"), CycleIssue, "cycle_id", "cycle", "cycles"),
        (plan.get("modules"), ModuleIssue, "module_id", "module", "modules"),
    ):
        if not enabled:
            tally.note(f"work_items:{label}-not-copied")
            continue
        rows = []
        for issue_id, old_id in model.objects.filter(issue_id__in=source_ids).values_list("issue_id", field_name):
            new_id = remap.get(namespace, old_id)
            if new_id is None:
                continue
            rows.append(model(issue_id=ids[issue_id], **{field_name: new_id}, **stamp))
        model.objects.bulk_create(rows, batch_size=BATCH_SIZE)
        tally.add(f"{label}_membership", len(rows))


def copy_property_values(*, source_project_id, target_project, ids, tally: CopyTally) -> None:
    """Custom work-item property values.

    ``property_id`` and ``value_option_id`` are kept verbatim, which is correct
    and not an oversight: ``IssueProperty`` hangs off ``IssueType``, which is
    workspace-level, so a copy inside the same workspace needs no property or
    option rows of its own. Copying them would collide with the unique index on
    (issue_type, display_name).
    """
    source_ids = list(ids)
    if not source_ids:
        return

    # A value whose property does not belong to the item's type is already
    # hidden in the source; the copy should not inherit it.
    types = dict(Issue.objects.filter(id__in=source_ids).values_list("id", "type_id"))
    members = set(
        ProjectMember.objects.filter(project=target_project, is_active=True).values_list("member_id", flat=True)
    )

    rows, stale, dropped_members = [], 0, 0
    for value in IssuePropertyValue.objects.filter(issue_id__in=source_ids).select_related("property"):
        if value.property.issue_type_id != types.get(value.issue_id):
            stale += 1
            continue
        if value.value_member_id and value.value_member_id not in members:
            dropped_members += 1
            continue
        rows.append(
            IssuePropertyValue(
                issue_id=ids[value.issue_id],
                property_id=value.property_id,
                project=target_project,
                workspace_id=target_project.workspace_id,
                value_text=value.value_text,
                value_number=value.value_number,
                value_boolean=value.value_boolean,
                value_date=value.value_date,
                value_option_id=value.value_option_id,
                value_member_id=value.value_member_id,
            )
        )

    IssuePropertyValue.objects.bulk_create(rows, batch_size=BATCH_SIZE)
    tally.add("property_values", len(rows))
    if stale:
        tally.add("property_values_stale", stale)
    if dropped_members:
        tally.add("property_members_dropped", dropped_members)
        tally.note("work_items:property-members-not-in-copy")


def copy_relations(*, source_project_id, target_project, ids, tally: CopyTally) -> None:
    """Relations, but only where both ends were copied.

    Both foreign keys point at ``Issue`` with nothing scoping them to a project,
    so copying a one-sided relation would attach the copy's items to the
    source's. A member of the copy would then see a "blocked by" they cannot
    open, and the source's items would start showing relations into a project
    their members have never heard of.
    """
    source_ids = set(ids)
    if not source_ids:
        return

    rows, dropped = [], 0
    for relation in IssueRelation.objects.filter(issue_id__in=source_ids):
        if relation.related_issue_id not in source_ids:
            dropped += 1
            continue
        rows.append(
            IssueRelation(
                issue_id=ids[relation.issue_id],
                related_issue_id=ids[relation.related_issue_id],
                relation_type=relation.relation_type,
                project=target_project,
                workspace_id=target_project.workspace_id,
            )
        )

    IssueRelation.objects.bulk_create(rows, batch_size=BATCH_SIZE, ignore_conflicts=True)
    tally.add("relations", len(rows))
    if dropped:
        tally.add("relations_dropped", dropped)
        tally.note("work_items:relations-outside-copy")


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

LEASE_SECONDS = 300


def claim(job, task_id: str):
    """Take the lease, or return None because somebody else holds it.

    Re-read under a row lock so two workers handed the same job by a redelivered
    message cannot both decide they own it.
    """
    from plane.ext.models import ProjectCopyJob

    with transaction.atomic():
        current = ProjectCopyJob.objects.select_for_update().get(pk=job.pk)
        now = timezone.now()
        held = current.lease_token is not None and current.lease_expires_at and current.lease_expires_at > now
        if current.is_terminal or held:
            return None

        current.status = ProjectCopyJob.Status.PROCESSING
        current.lease_token = uuid.uuid4()
        current.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        current.heartbeat_at = now
        current.started_at = current.started_at or now
        current.celery_task_id = task_id or ""
        current.attempt_count = current.attempt_count + 1
        current.save(
            update_fields=[
                "status",
                "lease_token",
                "lease_expires_at",
                "heartbeat_at",
                "started_at",
                "celery_task_id",
                "attempt_count",
                "updated_at",
            ]
        )
        return current


def still_ours(job) -> bool:
    """Whether this worker still holds the lease it claimed."""
    from plane.ext.models import ProjectCopyJob

    return ProjectCopyJob.objects.filter(pk=job.pk, lease_token=job.lease_token).exists()


def copy_work_items(job) -> CopyTally:
    """Copy every work item the job's plan asks for, resuming if need be.

    Each batch commits its rows, the counter and the cursor together, so a
    worker killed between them is impossible: either all three landed or none
    did. Anything already present in the target is skipped, which is what makes
    a redispatched job add the remainder rather than a second copy.
    """
    from plane.ext.models import ProjectCopyJob

    plan = job.plan or {}
    remap = StoredRemap(job.remap)
    tally = CopyTally()
    target = job.target_project

    type_ids = _available_type_ids(target)
    already = existing_sequence_ids(target.id)

    pending = source_work_items(job.source_project_id).exclude(sequence_id__in=already)
    batch = []
    for source in pending.iterator(chunk_size=BATCH_SIZE):
        batch.append(source)
        if len(batch) < BATCH_SIZE:
            continue
        _commit_batch(job, batch, target, remap, type_ids)
        batch = []
        if not still_ours(job):
            return tally
    if batch:
        _commit_batch(job, batch, target, remap, type_ids)

    ids = translation(job.source_project_id, target.id)

    job.stage = ProjectCopyJob.Stage.PARENTS
    job.save(update_fields=["stage", "updated_at"])
    link_parents(source_project_id=job.source_project_id, target_project=target, tally=tally)

    job.stage = ProjectCopyJob.Stage.SATELLITES
    job.save(update_fields=["stage", "updated_at"])
    copy_satellites(
        source_project_id=job.source_project_id,
        target_project=target,
        ids=ids,
        remap=remap,
        plan=plan,
        tally=tally,
    )

    job.stage = ProjectCopyJob.Stage.PROPERTIES
    job.save(update_fields=["stage", "updated_at"])
    copy_property_values(source_project_id=job.source_project_id, target_project=target, ids=ids, tally=tally)

    job.stage = ProjectCopyJob.Stage.RELATIONS
    job.save(update_fields=["stage", "updated_at"])
    copy_relations(source_project_id=job.source_project_id, target_project=target, ids=ids, tally=tally)

    for note in ("comments", "attachments", "history", "worklogs"):
        tally.note(f"work_items:{note}-not-copied")

    return tally


def _commit_batch(job, sources, target, remap, type_ids) -> None:
    """One batch: the rows, the progress and the cursor, in one transaction."""
    with transaction.atomic():
        created = copy_issue_batch(
            sources=sources,
            target_project=target,
            remap=remap,
            type_ids=type_ids,
        )
        job.copied = job.copied + len(created)
        job.cursor = sources[-1].sequence_id
        job.heartbeat_at = timezone.now()
        job.lease_expires_at = job.heartbeat_at + timedelta(seconds=LEASE_SECONDS)
        job.save(update_fields=["copied", "cursor", "heartbeat_at", "lease_expires_at", "updated_at"])


def _available_type_ids(target) -> dict:
    """Work item types the copy can actually use, and its default."""
    from plane.db.models.issue_type import ProjectIssueType

    rows = ProjectIssueType.objects.filter(project=target).select_related("issue_type")
    available = set()
    default_id = None
    for row in rows:
        available.add(row.issue_type_id)
        if row.issue_type.is_default:
            default_id = row.issue_type_id
    return {"available": available, "default": default_id}
