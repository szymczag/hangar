# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Duplicate a project's configuration so a project can be used as a template.

Everything here is configuration, and it all happens inside one transaction:
states, labels, estimates, issue types, intake, members, and empty
cycles/modules/views. Pages are out of scope -- they carry content through the
S3 and live-server description pipeline and are copied one at a time by
``PageDuplicateEndpoint``.

Work items are copied too, but not here. They are unbounded, and this
transaction holds a lock on the workspace row for its whole duration, so
inserting thousands of them would stall project creation for everyone else in
the workspace. This module only reserves their numbers and records a job;
:mod:`plane.ext.services.work_item_copy` does the work afterwards.

Three rules hold for every step here, and breaking any of them is silent:

* ``bulk_create`` bypasses ``save()``, and ``ProjectBaseModel.save()`` is the
  only thing that normally populates ``workspace``. Every bulk insert goes
  through :func:`_stamp`.
* ``external_source``/``external_id`` are cleared everywhere. ``Module`` (and
  ``Issue``, for later) carry a partial unique index on
  ``(project, external_source, external_id)`` for ``todoist_csv``; copying them
  verbatim would let a re-import skip rows it believes it already created.
* Ordering fields (``State.sequence``, ``Label.sort_order``, ``Cycle.sort_order``,
  ``Module.sort_order``) are copied verbatim rather than re-derived. A copy
  should reproduce the source's ordering, so bypassing the ``save()`` derivation
  is intentional, not an oversight.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field

from django.db import transaction
from django.db.models import Q

from plane.db.models import (
    Cycle,
    Estimate,
    EstimatePoint,
    Intake,
    IssueView,
    Label,
    Module,
    ModuleLink,
    ModuleMember,
    Project,
    ProjectIdentifier,
    ProjectMember,
    State,
    Workspace,
    WorkspaceMember,
)
from plane.db.models.issue_type import ProjectIssueType
from plane.ext.services.issue_types import ensure_project_system_types

# Copy options. Structure that defines "what a project is" is always copied;
# anything that grants access or carries someone else's work is opt-in.
ALWAYS_COPIED = ("states", "work_item_types")
OPTIONAL_DEFAULT_ON = ("labels", "estimates", "intake")
OPTIONAL_DEFAULT_OFF = ("members", "cycles", "modules", "views", "work_items")
COPY_OPTIONS = ALWAYS_COPIED + OPTIONAL_DEFAULT_ON + OPTIONAL_DEFAULT_OFF

# Beyond these a single transaction holds the workspace lock long enough to
# stall concurrent project creation. Crossing one is the signal to build the
# asynchronous path, not to raise the number.
MAX_MEMBERS = 200
MAX_CYCLES_AND_MODULES = 500
MAX_TOTAL_ROWS = 5000

# Work items are deliberately absent from the caps above. Those exist because
# the synchronous copy holds the workspace lock for its whole duration; work
# items are copied afterwards by a background job, outside that lock, so
# counting them there would refuse copies that are in fact cheap on it.
#
# This is a different kind of limit: not "try again with fewer options" but
# "there is no path", because the asynchronous path is already the fallback.
MAX_WORK_ITEMS = 20_000

# `IssueView.access` numbers PRIVATE as 0 and PUBLIC as 1. `Page.access` numbers
# them the other way round. Naming the one we use keeps the inversion from
# leaking into a filter that looks right.
VIEW_ACCESS_PUBLIC = 1

# Filter keys inside `IssueView.filters` that name project-scoped rows and must
# therefore be translated into the copy's ids or dropped.
REMAPPABLE_FILTER_KEYS = {
    "state": "state",
    "labels": "label",
    "cycle": "cycle",
    "module": "module",
}
# Filter keys that name users; kept only where the user is a member of the copy.
MEMBER_FILTER_KEYS = ("assignees", "created_by", "subscriber", "mentions")

# `rich_filters` is the representation the work item list actually queries with.
# Its keys are "<field>__<operator>"; these are the fields naming project-scoped
# rows, mapped to the remap namespace that holds their new ids.
RICH_FILTER_REMAPPABLE_FIELDS = {
    "state_id": "state",
    "label_id": "label",
    "cycle_id": "cycle",
    "module_id": "module",
}
RICH_FILTER_MEMBER_FIELDS = ("assignee_id", "mention_id", "created_by_id")


class ProjectCopyError(Exception):
    """A copy that cannot proceed, carrying the code the API should report."""

    def __init__(self, code: str, status_code: int = 400, detail=None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.detail = detail


@dataclass
class CopyPlan:
    """Normalised copy options. Absent keys fall back to the documented default."""

    states: bool = True
    work_item_types: bool = True
    labels: bool = True
    estimates: bool = True
    intake: bool = True
    members: bool = False
    cycles: bool = False
    modules: bool = False
    views: bool = False
    # Off by default like everything that carries other people's work, and by
    # far the most expensive option: it is the only one copied asynchronously.
    work_items: bool = False

    @classmethod
    def from_options(cls, options: dict | None) -> "CopyPlan":
        plan = cls(**{key: value for key, value in (options or {}).items() if key in COPY_OPTIONS})
        # Structure is not optional: a project without states cannot hold work.
        plan.states = True
        plan.work_item_types = True
        return plan


@dataclass
class CopyResult:
    project: Project
    counts: dict = field(default_factory=dict)
    skipped: list = field(default_factory=list)
    # ProjectMember rows the caller's copy created for *other* people; the view
    # mails them after commit.
    notify_member_ids: list = field(default_factory=list)
    # The source's cover, for the view to copy once the transaction has
    # committed. An S3 copy cannot be rolled back with the database, so it must
    # not happen inside it.
    cover_source_asset_id: uuid.UUID | None = None
    # Set when work items were asked for. The view dispatches the job after the
    # transaction commits; a task starting sooner would find no rows.
    work_item_job_id: uuid.UUID | None = None


class _Remap:
    """Old primary key -> new primary key, kept one namespace per model."""

    def __init__(self):
        self._entries: dict[str, dict] = {}

    def put(self, label: str, old_id, new_id) -> None:
        self._entries.setdefault(label, {})[str(old_id)] = new_id

    def get(self, label: str, old_id):
        if old_id is None:
            return None
        return self._entries.get(label, {}).get(str(old_id))

    def translate(self, label: str, old_ids) -> list:
        """Map a list of ids, dropping any that were not copied."""
        translated = [self.get(label, old_id) for old_id in old_ids or []]
        return [str(new_id) for new_id in translated if new_id is not None]

    def as_dict(self) -> dict:
        """A JSON-storable copy, for a job that runs after this request ends.

        The work item copy is asynchronous, so the translation built here has to
        outlive the transaction that built it.
        """
        return {label: {str(old): str(new) for old, new in entries.items()} for label, entries in self._entries.items()}


@dataclass
class _Context:
    source: Project
    target: Project
    actor: object
    plan: CopyPlan
    remap: _Remap
    result: CopyResult

    def record(self, label: str, count: int) -> None:
        if count:
            self.result.counts[label] = count

    def skip(self, reason: str) -> None:
        if reason not in self.result.skipped:
            self.result.skipped.append(reason)


def _stamp(rows, context: _Context):
    """Set the fields ``bulk_create`` would otherwise leave empty.

    ``ProjectBaseModel.save()``/``WorkspaceBaseModel.save()`` derive ``workspace``
    from ``project``; ``bulk_create`` never calls them.
    """
    for row in rows:
        row.project = context.target
        row.workspace_id = context.target.workspace_id
        # `created_by` only, matching `BaseModel.save()`, which leaves
        # `updated_by` unset on creation.
        row.created_by = context.actor
    return rows


# --------------------------------------------------------------------------
# name and identifier derivation
# --------------------------------------------------------------------------


def _name_is_free(workspace_id, name: str) -> bool:
    return not Project.objects.filter(workspace_id=workspace_id, name=name, deleted_at__isnull=True).exists()


def _identifier_is_free(workspace_id, identifier: str) -> bool:
    return not Project.objects.filter(
        workspace_id=workspace_id, identifier=identifier, deleted_at__isnull=True
    ).exists()


def derive_name(workspace_id, base_name: str, limit: int = 50) -> str:
    """``Foo`` -> ``Foo (Copy)`` -> ``Foo (Copy 2)`` ... within the name column."""
    max_length = Project._meta.get_field("name").max_length
    trimmed = base_name[: max_length - len(" (Copy 99)")].rstrip()

    for attempt in range(1, limit + 1):
        suffix = " (Copy)" if attempt == 1 else f" (Copy {attempt})"
        candidate = f"{trimmed}{suffix}"
        if _name_is_free(workspace_id, candidate):
            return candidate

    raise ProjectCopyError("PROJECT_NAME_ALREADY_EXIST")


def derive_identifier(workspace_id, base_identifier: str, limit: int = 100) -> str:
    """``FOO`` -> ``FOO1`` -> ``FOO2`` ... respecting the identifier column width."""
    max_length = Project._meta.get_field("identifier").max_length
    base = (base_identifier or "PROJ").upper()

    for attempt in range(1, limit + 1):
        suffix = str(attempt)
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        if _identifier_is_free(workspace_id, candidate):
            return candidate

    # Fall back to randomness rather than looping forever on a crowded workspace.
    for _ in range(limit):
        candidate = f"{base[: max_length - 4]}{uuid.uuid4().hex[:4].upper()}"
        if _identifier_is_free(workspace_id, candidate):
            return candidate

    raise ProjectCopyError("PROJECT_IDENTIFIER_ALREADY_EXIST")


# --------------------------------------------------------------------------
# admission
# --------------------------------------------------------------------------


def _planned_counts(source: Project, actor, plan: CopyPlan) -> dict:
    """Count what this caller's copy would actually create.

    The view count applies the same predicate ``_copy_views`` does. Counting
    every view instead would both over-count -- refusing a copy that would in
    fact be small -- and report, through the admission error, how many private
    views other members hold. No other endpoint discloses that.
    """
    counts = {
        "states": State.all_state_objects.filter(project=source, deleted_at__isnull=True).count(),
        "labels": Label.objects.filter(project=source).count() if plan.labels else 0,
        "estimates": Estimate.objects.filter(project=source).count() if plan.estimates else 0,
        "members": ProjectMember.objects.filter(project=source, is_active=True).count() if plan.members else 0,
        "cycles": Cycle.objects.filter(project=source).count() if plan.cycles else 0,
        "modules": Module.objects.filter(project=source).count() if plan.modules else 0,
        "views": _copyable_views(source, actor).count() if plan.views else 0,
    }
    return counts


def _admit(source: Project, actor, plan: CopyPlan) -> None:
    counts = _planned_counts(source, actor, plan)

    # The limit that was exceeded is what the caller needs; the per-model tally
    # is not, so it stays out of the error body.
    if counts["members"] > MAX_MEMBERS:
        raise ProjectCopyError("PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY", detail={"limit": "members"})
    if counts["cycles"] + counts["modules"] > MAX_CYCLES_AND_MODULES:
        raise ProjectCopyError("PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY", detail={"limit": "cycles_and_modules"})
    if sum(counts.values()) > MAX_TOTAL_ROWS:
        raise ProjectCopyError("PROJECT_TOO_LARGE_TO_COPY_SYNCHRONOUSLY", detail={"limit": "total_rows"})


# --------------------------------------------------------------------------
# per-model steps
# --------------------------------------------------------------------------

# Scalar project fields that describe what the project *is*. Deliberately an
# allow-list: a field added by a future upstream sync should default to not
# copied rather than copied and wrong.
PROJECT_SCALAR_FIELDS = (
    "description",
    "description_text",
    "description_html",
    "emoji",
    "icon_prop",
    "logo_props",
    "cover_image",
    "module_view",
    "cycle_view",
    "issue_views_view",
    "page_view",
    "intake_view",
    "is_time_tracking_enabled",
    "is_issue_type_enabled",
    "guest_view_all_features",
    "archive_in",
    "close_in",
    "timezone",
)


def _create_target_project(source: Project, actor, name: str, identifier: str, network: int) -> Project:
    """Create the destination row.

    Not ``pk = None; save()``: a re-insert silently carries ``default_state_id``,
    ``estimate_id`` and ``cover_image_asset_id`` pointing at the *source's* rows,
    a cross-project foreign key nothing would catch.
    """
    scalars = {name_: getattr(source, name_) for name_ in PROJECT_SCALAR_FIELDS}

    target = Project.objects.create(
        workspace=source.workspace,
        name=name,
        identifier=identifier,
        network=network,
        # `project_lead` is the caller, never the source's lead: carrying it over
        # would put a third party in charge of a project they may not be in.
        project_lead=actor,
        default_assignee=None,
        # Back-patched once states and estimates exist.
        default_state=None,
        estimate=None,
        # Copied post-commit, because an S3 object copy cannot be rolled back.
        cover_image_asset=None,
        external_source=None,
        external_id=None,
        archived_at=None,
        created_by=actor,
        **scalars,
    )

    # `ProjectSerializer.create` is the only other place this row is made, and a
    # project without it has no work-item identifier.
    ProjectIdentifier.objects.create(
        name=target.identifier,
        project=target,
        workspace_id=target.workspace_id,
        created_by=actor,
    )
    return target


def _copy_states(context: _Context) -> None:
    # `State.objects` is a manager that EXCLUDES triage states; using it drops
    # the triage state silently and breaks intake on the copy. `all_state_objects`
    # is a bare Manager, so it also returns soft-deleted rows -- hence the filter.
    sources = list(State.all_state_objects.filter(project=context.source, deleted_at__isnull=True).order_by("sequence"))

    rows = [
        State(
            name=source.name,
            description=source.description,
            color=source.color,
            slug=source.slug,
            sequence=source.sequence,
            group=source.group,
            is_triage=source.is_triage,
            default=source.default,
            external_source=None,
            external_id=None,
        )
        for source in sources
    ]
    created = State.objects.bulk_create(_stamp(rows, context), batch_size=500)

    for source, row in zip(sources, created):
        context.remap.put("state", source.id, row.id)
    context.record("states", len(created))


def _copy_work_item_types(context: _Context) -> None:
    # IssueType rows are workspace-scoped and uniquely keyed on
    # (workspace, system_key); they are re-linked, never copied.
    ensure_project_system_types(context.target)

    system_type_ids = set(
        ProjectIssueType.objects.filter(project=context.target).values_list("issue_type_id", flat=True)
    )
    sources = ProjectIssueType.objects.filter(project=context.source).exclude(issue_type_id__in=system_type_ids)

    rows = [
        ProjectIssueType(issue_type_id=source.issue_type_id, level=source.level, is_default=source.is_default)
        for source in sources
    ]
    created = ProjectIssueType.objects.bulk_create(_stamp(rows, context), batch_size=500)
    context.record("work_item_types", len(created) + len(system_type_ids))


def _copy_labels(context: _Context) -> None:
    sources = list(Label.objects.filter(project=context.source).order_by("sort_order"))

    # Two passes: `parent` is a self reference, so it can only be resolved once
    # every label in the copy has an id.
    rows = [
        Label(
            name=source.name,
            description=source.description,
            color=source.color,
            sort_order=source.sort_order,
            parent=None,
            external_source=None,
            external_id=None,
        )
        for source in sources
    ]
    created = Label.objects.bulk_create(_stamp(rows, context), batch_size=500)

    for source, row in zip(sources, created):
        context.remap.put("label", source.id, row.id)

    reparented = []
    for source, row in zip(sources, created):
        if source.parent_id is None:
            continue
        new_parent_id = context.remap.get("label", source.parent_id)
        if new_parent_id is None:
            continue
        row.parent_id = new_parent_id
        reparented.append(row)

    if reparented:
        Label.objects.bulk_update(reparented, ["parent"], batch_size=500)
    context.record("labels", len(created))


def _copy_estimates(context: _Context) -> None:
    sources = list(Estimate.objects.filter(project=context.source))

    rows = [
        Estimate(name=source.name, description=source.description, type=source.type, last_used=source.last_used)
        for source in sources
    ]
    created = Estimate.objects.bulk_create(_stamp(rows, context), batch_size=500)

    for source, row in zip(sources, created):
        context.remap.put("estimate", source.id, row.id)

    point_rows = []
    point_sources = []
    for point in EstimatePoint.objects.filter(project=context.source):
        new_estimate_id = context.remap.get("estimate", point.estimate_id)
        if new_estimate_id is None:
            continue
        point_sources.append(point)
        point_rows.append(
            EstimatePoint(estimate_id=new_estimate_id, key=point.key, description=point.description, value=point.value)
        )

    created_points = EstimatePoint.objects.bulk_create(_stamp(point_rows, context), batch_size=500)

    # Work items point at an estimate *point*, not at the estimate, so the copy
    # needs this translation too. Recording only "estimate" was enough while
    # nothing carried an `estimate_point_id` across.
    for source, row in zip(point_sources, created_points):
        context.remap.put("estimate_point", source.id, row.id)
    context.record("estimates", len(created))
    context.record("estimate_points", len(point_rows))


def _copy_intake(context: _Context) -> None:
    sources = list(Intake.objects.filter(project=context.source))

    rows = [
        Intake(
            # Mirrors the naming `ProjectViewSet` uses when it provisions intake.
            name=f"{context.target.name} Intake" if source.is_default else source.name,
            description=source.description,
            is_default=source.is_default,
            view_props=source.view_props,
            logo_props=source.logo_props,
        )
        for source in sources
    ]
    created = Intake.objects.bulk_create(_stamp(rows, context), batch_size=500)
    context.record("intake", len(created))


def _capped_role(source_role: int, workspace_role: int) -> int:
    """Keep a copied project role consistent with the member's workspace role.

    `ProjectMemberViewSet.create` refuses the combinations outright: a workspace
    ADMIN may not hold a lower project role, and a workspace GUEST may not hold a
    higher one. A copy cannot refuse -- the source row already exists -- so it
    clamps instead, and reports `members:role-adjusted`.
    """
    from plane.app.permissions import ROLE

    if workspace_role == ROLE.ADMIN.value:
        return ROLE.ADMIN.value
    if workspace_role == ROLE.GUEST.value:
        return ROLE.GUEST.value
    return source_role


def _copy_members(context: _Context) -> None:
    """Add the caller as ADMIN, and optionally mirror the source's membership.

    Uses ``save()`` rather than ``bulk_create``: ``ProjectMember.save()`` creates
    the matching ``ProjectUserProperty``, without which a member has no sidebar
    ordering for the project.
    """
    from plane.app.permissions import ROLE

    ProjectMember.objects.create(
        project=context.target,
        workspace_id=context.target.workspace_id,
        member=context.actor,
        role=ROLE.ADMIN.value,
        created_by=context.actor,
    )
    created = 1

    if context.plan.members:
        sources = ProjectMember.objects.filter(project=context.source, is_active=True, member__isnull=False).exclude(
            member_id=context.actor.id
        )
        workspace_roles = dict(
            WorkspaceMember.objects.filter(
                workspace_id=context.target.workspace_id,
                member_id__in=[source.member_id for source in sources],
                is_active=True,
            ).values_list("member_id", "role")
        )
        adjusted = False

        for source in sources:
            workspace_role = workspace_roles.get(source.member_id)
            if workspace_role is None:
                # No longer in the workspace; the source row is stale.
                context.skip("members:not-in-workspace")
                continue

            role = _capped_role(source.role, workspace_role)
            adjusted = adjusted or role != source.role

            member = ProjectMember.objects.create(
                project=context.target,
                workspace_id=context.target.workspace_id,
                member_id=source.member_id,
                role=role,
                view_props=source.view_props,
                default_props=source.default_props,
                preferences=source.preferences,
                created_by=context.actor,
            )
            # The view mails these once the transaction commits, matching what
            # `ProjectMemberViewSet.create` does. Nobody should find themselves
            # in a project without being told.
            context.result.notify_member_ids.append(member.id)
            created += 1

        if adjusted:
            context.skip("members:role-adjusted")

    context.record("members", created)


def _target_member_ids(context: _Context) -> set:
    return {
        str(member_id)
        for member_id in ProjectMember.objects.filter(project=context.target, is_active=True).values_list(
            "member_id", flat=True
        )
    }


def _copy_cycles(context: _Context) -> None:
    sources = list(Cycle.objects.filter(project=context.source).order_by("sort_order"))

    rows = [
        Cycle(
            name=source.name,
            description=source.description,
            start_date=source.start_date,
            end_date=source.end_date,
            # The caller owns every copied cycle; the source's owner did not ask
            # to own anything in a new project.
            owned_by=context.actor,
            view_props=source.view_props,
            sort_order=source.sort_order,
            logo_props=source.logo_props,
            timezone=source.timezone,
            # Runtime state, not configuration.
            progress_snapshot={},
            archived_at=None,
            version=1,
            external_source=None,
            external_id=None,
        )
        for source in sources
    ]
    created = Cycle.objects.bulk_create(_stamp(rows, context), batch_size=500)

    for source, row in zip(sources, created):
        context.remap.put("cycle", source.id, row.id)
    context.record("cycles", len(created))


def _copy_modules(context: _Context) -> None:
    sources = list(Module.objects.filter(project=context.source).order_by("sort_order"))
    member_ids = _target_member_ids(context)

    rows = [
        Module(
            name=source.name,
            description=source.description,
            description_text=source.description_text,
            description_html=source.description_html,
            start_date=source.start_date,
            target_date=source.target_date,
            status=source.status,
            # A lead who is not in the copy would be an unreachable assignment.
            lead_id=source.lead_id if str(source.lead_id) in member_ids else None,
            view_props=source.view_props,
            sort_order=source.sort_order,
            logo_props=source.logo_props,
            archived_at=None,
            # Required: `todoist_module_external_uidx` keys on these.
            external_source=None,
            external_id=None,
        )
        for source in sources
    ]
    created = Module.objects.bulk_create(_stamp(rows, context), batch_size=500)

    for source, row in zip(sources, created):
        context.remap.put("module", source.id, row.id)

    link_rows = []
    for link in ModuleLink.objects.filter(project=context.source):
        new_module_id = context.remap.get("module", link.module_id)
        if new_module_id is None:
            continue
        link_rows.append(ModuleLink(module_id=new_module_id, title=link.title, url=link.url, metadata=link.metadata))
    ModuleLink.objects.bulk_create(_stamp(link_rows, context), batch_size=500)

    membership_rows = []
    for membership in ModuleMember.objects.filter(project=context.source):
        new_module_id = context.remap.get("module", membership.module_id)
        if new_module_id is None or str(membership.member_id) not in member_ids:
            continue
        membership_rows.append(ModuleMember(module_id=new_module_id, member_id=membership.member_id))
    ModuleMember.objects.bulk_create(_stamp(membership_rows, context), batch_size=500)

    context.record("modules", len(created))
    context.record("module_links", len(link_rows))
    context.record("module_members", len(membership_rows))


def _copyable_views(source: Project, actor):
    """The views of ``source`` this actor may carry into a copy.

    `IssueView.access` numbers PRIVATE as 0 and PUBLIC as 1 -- the inverse of
    `Page.access`. Shared by the copy step and by admission counting, so the two
    can never disagree about which views exist.
    """
    return IssueView.objects.filter(project=source, archived_at__isnull=True).filter(
        Q(access=VIEW_ACCESS_PUBLIC) | Q(owned_by_id=actor.id)
    )


def _remap_rich_filters(rich_filters: dict, context: _Context, member_ids: set) -> tuple[dict, bool]:
    """Translate project-scoped ids inside a rich filter into the copy's ids.

    ``rich_filters`` is the representation the work item list actually queries
    with -- the legacy ``filters`` blob below is no longer what the UI reads --
    so a copy that remaps only ``filters`` produces views that quietly match
    nothing. Keys are ``"<field>__<operator>"`` (``state_id__in``) and values are
    a list or a single value.
    """
    if not isinstance(rich_filters, dict):
        return {}, False

    remapped = {}
    dropped = False

    for key, value in rich_filters.items():
        field = key.split("__", 1)[0]
        values = value if isinstance(value, list) else [value]

        if field in RICH_FILTER_REMAPPABLE_FIELDS:
            translated = context.remap.translate(RICH_FILTER_REMAPPABLE_FIELDS[field], values)
            if len(translated) != len(values):
                dropped = True
            if translated:
                remapped[key] = translated if isinstance(value, list) else translated[0]
            continue

        if field in RICH_FILTER_MEMBER_FIELDS:
            kept = [str(item) for item in values if str(item) in member_ids]
            if len(kept) != len(values):
                dropped = True
            if kept:
                remapped[key] = kept if isinstance(value, list) else kept[0]
            continue

        if field == "project_id":
            # The copy is its own project; pointing at the source would filter
            # every work item away.
            remapped[key] = [str(context.target.id)] if isinstance(value, list) else str(context.target.id)
            continue

        remapped[key] = value

    return remapped, dropped


def _remap_view_filters(filters: dict, context: _Context, member_ids: set) -> tuple[dict, bool]:
    """Translate project-scoped ids inside a saved filter into the copy's ids.

    A filter carried over verbatim names the *source's* states and labels, so the
    copied view silently matches nothing. Values with no counterpart are dropped.
    """
    if not isinstance(filters, dict):
        return {}, False

    remapped = {}
    dropped = False

    for key, value in filters.items():
        if key in REMAPPABLE_FILTER_KEYS and isinstance(value, list):
            translated = context.remap.translate(REMAPPABLE_FILTER_KEYS[key], value)
            if len(translated) != len(value):
                dropped = True
            if translated:
                remapped[key] = translated
            continue

        if key in MEMBER_FILTER_KEYS and isinstance(value, list):
            kept = [str(item) for item in value if str(item) in member_ids]
            if len(kept) != len(value):
                dropped = True
            if kept:
                remapped[key] = kept
            continue

        remapped[key] = value

    return remapped, dropped


def _copy_views(context: _Context) -> None:
    # Copying someone else's private view would disclose it; `_copyable_views`
    # owns that predicate so admission counting cannot drift from it.
    sources = list(_copyable_views(context.source, context.actor))
    if IssueView.objects.filter(project=context.source, archived_at__isnull=True).count() > len(sources):
        context.skip("views:private")

    member_ids = _target_member_ids(context)
    created = 0
    dropped_any = False

    for source in sources:
        filters, dropped = _remap_view_filters(source.filters, context, member_ids)
        rich_filters, rich_dropped = _remap_rich_filters(source.rich_filters, context, member_ids)
        dropped_any = dropped_any or dropped or rich_dropped

        # `save()`, not `bulk_create`: `IssueView.save()` recomputes `query` from
        # `filters`, and a `query` blob copied verbatim still points at the source.
        view = IssueView(
            workspace_id=context.target.workspace_id,
            project=context.target,
            name=source.name,
            description=source.description,
            filters=filters,
            display_filters=source.display_filters,
            display_properties=source.display_properties,
            rich_filters=rich_filters,
            access=source.access,
            logo_props=source.logo_props,
            owned_by=context.actor,
            is_locked=False,
            archived_at=None,
            created_by=context.actor,
            query={},
        )
        view.save()
        created += 1

    if dropped_any:
        context.skip("views:unmapped-filters")
    context.record("views", created)


def _backpatch_project(context: _Context) -> None:
    """Point the project's own foreign keys at the copy's rows, never the source's."""
    updates = {}

    new_default_state_id = context.remap.get("state", context.source.default_state_id)
    if new_default_state_id is not None:
        updates["default_state_id"] = new_default_state_id

    new_estimate_id = context.remap.get("estimate", context.source.estimate_id)
    if new_estimate_id is not None:
        updates["estimate_id"] = new_estimate_id

    if context.source.default_assignee_id and str(context.source.default_assignee_id) in _target_member_ids(context):
        updates["default_assignee_id"] = context.source.default_assignee_id

    if updates:
        Project.objects.filter(pk=context.target.pk).update(**updates)
        for attribute, value in updates.items():
            setattr(context.target, attribute, value)


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


@transaction.atomic
def duplicate_project(*, source: Project, actor, name=None, identifier=None, network=None, options=None) -> CopyResult:
    """Copy ``source``'s configuration into a new project owned by ``actor``.

    The caller is responsible for authorising both the read of ``source`` and the
    creation of a project in its workspace; this function assumes both.
    """
    plan = CopyPlan.from_options(options)

    if source.archived_at is not None:
        raise ProjectCopyError("PROJECT_ARCHIVED")

    # Serialises name/identifier derivation against concurrent project creation.
    # `ensure_project_system_types` takes the same lock, so the two nest rather
    # than deadlock.
    Workspace.objects.select_for_update().get(pk=source.workspace_id)

    _admit(source, actor, plan)

    resolved_name = name or derive_name(source.workspace_id, source.name)
    resolved_identifier = identifier or derive_identifier(source.workspace_id, source.identifier)

    if not _name_is_free(source.workspace_id, resolved_name):
        raise ProjectCopyError("PROJECT_NAME_ALREADY_EXIST")
    if not _identifier_is_free(source.workspace_id, resolved_identifier):
        raise ProjectCopyError("PROJECT_IDENTIFIER_ALREADY_EXIST")

    target = _create_target_project(
        source,
        actor,
        resolved_name,
        resolved_identifier,
        source.network if network is None else network,
    )

    context = _Context(
        source=source,
        target=target,
        actor=actor,
        plan=plan,
        remap=_Remap(),
        result=CopyResult(project=target, cover_source_asset_id=source.cover_image_asset_id),
    )

    _copy_states(context)
    _copy_work_item_types(context)
    # Members before modules and views, which filter on who is in the copy.
    _copy_members(context)

    if plan.labels:
        _copy_labels(context)
    if plan.estimates:
        _copy_estimates(context)
    if plan.intake and source.intake_view:
        _copy_intake(context)
    if plan.cycles:
        _copy_cycles(context)
    if plan.modules:
        _copy_modules(context)
    if plan.views:
        _copy_views(context)

    _backpatch_project(context)

    # Never copied, and worth reporting so the operator knows to re-attach them:
    # a webhook would start posting a new project's events to an endpoint whose
    # owner never asked for them.
    context.skip("webhooks:not-copied")

    if plan.work_items:
        _queue_work_item_copy(context)
    else:
        context.skip("work_items:not-copied")

    return context.result


def _queue_work_item_copy(context: _Context) -> None:
    """Reserve the work item numbers and record the job, before committing.

    Both belong inside this transaction. The reservation has to be in place
    before anyone can create a work item in the copy, and a committed project
    that asked for work items must never exist without a job to bring them --
    the sweeper finds a queued job, but it cannot invent one.

    Dispatching is the caller's job, after commit: a task that starts before the
    transaction commits would find no rows.
    """
    from plane.ext.models import ProjectCopyJob
    from plane.ext.services.work_item_copy import reserve_sequence_range, source_work_items

    total = source_work_items(context.source.id).count()
    if total > MAX_WORK_ITEMS:
        raise ProjectCopyError("PROJECT_TOO_LARGE_TO_COPY", detail={"limit": "work_items"})

    reserve_sequence_range(context.target, context.source.id)

    job = ProjectCopyJob.objects.create(
        workspace_id=context.target.workspace_id,
        source_project=context.source,
        target_project=context.target,
        initiated_by=context.actor,
        plan=asdict(context.plan),
        remap=context.remap.as_dict(),
        total=total,
    )
    context.result.work_item_job_id = job.id
    context.result.counts["work_items_planned"] = total


__all__ = [
    "COPY_OPTIONS",
    "CopyPlan",
    "CopyResult",
    "ProjectCopyError",
    "derive_identifier",
    "derive_name",
    "duplicate_project",
]
