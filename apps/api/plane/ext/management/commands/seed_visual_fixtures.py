# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Build the fixed world the visual regression suite screenshots.

Everything here is pinned. Identifiers are literals so specs can hardcode URLs;
timestamps are written explicitly, because `auto_now_add` would otherwise make
every baseline a function of when it was taken; and the clock the browser is
given comes from the same constant the rows are anchored to, so the two cannot
disagree.

It writes a manifest the Playwright container reads, including the session
cookies. That direction matters: the seed owns the data, so the seed describes
it. The alternative -- tests declaring what they expect to exist -- is two
descriptions that have to be kept in agreement.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.db import transaction

from plane.db.models import (
    Cycle,
    DeployBoard,
    Intake,
    IntakeIssue,
    Issue,
    IssueActivity,
    IssueComment,
    IssueType,
    IssueLabel,
    IssueView,
    IssueSequence,
    Label,
    Module,
    Profile,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberInvite,
    WorkspaceUserPreference,
)
from plane.bgtasks.issue_activities_task import _format_worklog_duration
from plane.ext.auth.sessions import mint_admin_session, mint_app_session
from plane.ext.models import (
    ImportJob,
    InstanceMaintenanceNotice,
    IssueProperty,
    IssuePropertyOption,
    IssuePropertyValue,
    IssueWorkLog,
    ProjectCopyJob,
    PropertyTypeChoices,
    WorkspaceSharedLink,
    WorkspaceSharedLinkHide,
)
from plane.ext.services.issue_types import ensure_project_system_types
from plane.license.models import InstanceAdmin, Instance
from plane.utils.cache import invalidate_cache_directly

# The one instant everything is anchored to. Handed to the browser as well, so a
# relative timestamp rendered in the interface is stable rather than a slow leak
# that fails the suite on a schedule.
CLOCK = datetime(2026, 1, 15, 12, 0, 0, tzinfo=dt_timezone.utc)
WORKSHOP_ISSUE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000090")
# `TrainerProfile` declares no ordering and `TrainerListEndpoint` sorts by `id`,
# which is a random UUID. Left to itself the ledger listed the two trainers in
# whichever order the seed happened to generate, so four baselines flipped
# between runs -- stable within a run, different the next time, which is the
# shape of a flake that looks like a real change. Pinned in seed order, the way
# the workspace, project and work item numbers already are.
TRAINER_PROFILE_IDS = {
    "light": uuid.UUID("a0000000-0000-4000-8000-000000000091"),
    "dark": uuid.UUID("a0000000-0000-4000-8000-000000000092"),
}
# The same problem one table over, and the one the first fix missed: the session
# editor lists its trainers from the work item's assignees, and `IssueAssignee`
# rows are ordered by their own random id. Pinning the trainer profiles fixed the
# ledger and the planner while leaving the checkboxes free to swap.
ASSIGNEE_IDS = {
    "light": uuid.UUID("a0000000-0000-4000-8000-000000000093"),
    "dark": uuid.UUID("a0000000-0000-4000-8000-000000000094"),
}

# Work item lists aggregate `assignee_ids` in `assignees__id` order, which is the
# users' own random ids. The 1.4 avatars printed one initial ("V" for all three
# users), so the order never showed; the Propel avatar group prints two ("VD",
# "VL"), and a work item assigned to two people swapped them between fresh
# databases.
USER_IDS = {
    "light": uuid.UUID("a0000000-0000-4000-8000-000000000097"),
    "dark": uuid.UUID("a0000000-0000-4000-8000-000000000098"),
    "admin": uuid.UUID("a0000000-0000-4000-8000-000000000099"),
}

ADMIN, MEMBER = 20, 15

WORKSPACE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
PROJECT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000002")
COPY_TARGET_ID = uuid.UUID("a0000000-0000-4000-8000-000000000003")
# The project behind the published board (apps/space). It has no members, so no
# signed-in story sees it in a sidebar or a project list; only the board does.
PUBLISHED_PROJECT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000004")
# `get_anchor` is a random hex string, and the board's URL is its anchor.
PUBLISHED_ANCHOR = "a0000000000040008000000000000004"
# The board lists a work item's labels in `labels__id` order, so random ids put
# "docs" and "release" in a different order on every fresh database.
PUBLISHED_LABEL_IDS = {
    "docs": uuid.UUID("a0000000-0000-4000-8000-000000000095"),
    "release": uuid.UUID("a0000000-0000-4000-8000-000000000096"),
}
# 24 hex characters, the shape `secrets.token_hex(12)` produces.
INSTANCE_ID = "a00000000000400080000000"
# One saved view in the project and one in the workspace, for the view list
# stories. Pinned like the projects, so a re-seed finds them rather than adding
# a second row the lists would then show.
PROJECT_VIEW_ID = uuid.UUID("a0000000-0000-4000-8000-000000000005")
WORKSPACE_VIEW_ID = uuid.UUID("a0000000-0000-4000-8000-000000000006")
# The cycles, the module and the intake work item the cycle, module and intake
# stories photograph, pinned for the same reason.
COMPLETED_CYCLE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000007")
DRAFT_CYCLE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000008")
MODULE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000009")
INTAKE_ID = uuid.UUID("a0000000-0000-4000-8000-00000000000a")
INTAKE_STATE_ID = uuid.UUID("a0000000-0000-4000-8000-00000000000b")
INTAKE_WORK_ITEM_ID = uuid.UUID("a0000000-0000-4000-8000-00000000000c")
INTAKE_ISSUE_ID = uuid.UUID("a0000000-0000-4000-8000-00000000000d")

# Enough to overflow a 900px viewport, which the layout story depends on.
#
# With a list that fits, `<main>` renders identically whether it is `h-full`,
# `flex-1`, or `flex-1 min-h-0` -- the flex item shrinks to the space left by
# the maintenance bar either way, nothing is clipped, and the story passes
# against all three. It only discriminates when the content is taller than the
# space available, which is exactly the situation the fix was for.
_WORK_ITEM_NAMES = [
    "Draft the onboarding guide",
    "Audit the export pipeline",
    "Rewrite the failure pages",
    "Retire the legacy importer",
    "Measure cold start",
    "Trim the sidebar",
    "Document the copy job",
    "Prune stale invitations",
    "Rotate the signing keys",
    "Backfill the search index",
    "Split the settings bundle",
    "Chase the flaky migration",
    "Cache the instance payload",
    "Deduplicate the webhooks",
    "Shrink the sidebar avatars",
    "Reword the empty states",
    "Batch the notification writes",
    "Drop the unused columns",
    "Pin the browser version",
    "Vendor the icon set",
    "Debounce the search box",
    "Expire the stale sessions",
    "Compress the export archive",
    "Repair the cycle burndown",
    "Guard the bulk endpoints",
    "Trim the docker context",
    "Align the modal paddings",
    "Retire the feature flag",
    "Collapse the duplicate routes",
    "Record the slow queries",
]
_PRIORITIES = ["urgent", "high", "high", "medium", "medium", "low", "low", "none"]

WORK_ITEMS = [(name, _PRIORITIES[index % len(_PRIORITIES)]) for index, name in enumerate(_WORK_ITEM_NAMES)]


class Command(BaseCommand):
    help = "Seed the fixed data the visual regression suite screenshots"

    def add_arguments(self, parser):
        parser.add_argument("--out", default=os.environ.get("VR_FIXTURES", "/vr/fixtures.json"))

    @transaction.atomic
    def handle(self, *args, **options):
        users = self._users()
        workspace = self._workspace(users["admin"])
        project = self._project(workspace, users)
        self._work_items(workspace, project, users["light"])
        self._work_item_properties(workspace, project)
        self._worklogs(workspace, project, users["light"])
        self._comments(workspace, project, users["light"])
        self._views(workspace, project, users["light"])
        self._cycles_and_modules(workspace, project, users["light"])
        self._intake(workspace, project, users["light"])
        self._shared_links(workspace, users)
        self._import_jobs(workspace, project, users["admin"])
        self._invitations(workspace, users["admin"])
        trainers = self._trainers(workspace, project, users)
        workshop = self._workshop(workspace, project, users)
        self._maintenance_notice()
        copy_target = self._copy_in_flight(workspace, project, users)
        published = self._published_board(workspace, users["admin"])

        manifest = {
            "clock": CLOCK.isoformat().replace("+00:00", "Z"),
            "workspace": {"slug": workspace.slug, "id": str(workspace.id)},
            "project": {"id": str(project.id), "identifier": project.identifier},
            "copyTarget": {"id": str(copy_target.id)},
            # The published board: its anchor, the work items it lists in order,
            # and the one the peek story opens.
            "publishedBoard": {
                "anchor": published.anchor,
                "workItems": [name for name, _, _, _ in Command.PUBLISHED_WORK_ITEMS],
                "peekId": str(Issue.objects.get(project_id=PUBLISHED_PROJECT_ID, sequence_id=1).id),
            },
            # The Workshop work item, so the session specs address it by id rather
            # than by hunting for its name in a list.
            "workshop": {"id": str(workshop.id), "name": workshop.name, "sessions": 3},
            # Published for the same reason as the work item names: a spec that
            # waits on a trainer should wait on the seeded one, not on a string
            # typed into the spec that drifts the moment the seed changes.
            "trainers": [profile.user.display_name for profile in trainers],
            # Published so a spec can wait on real seeded content rather than on
            # a string typed into the spec, which drifts from the seed silently.
            "workItems": [name for name, _ in WORK_ITEMS],
            # Published so the specs assert seeded content instead of strings
            "properties": [name for name, _, _ in Command.PROPERTIES],
            # The first work item's comment, which the work item detail stories wait on.
            "comment": Command.COMMENT,
            # The saved views the view list stories wait on.
            "views": {"project": Command.PROJECT_VIEW, "workspace": Command.WORKSPACE_VIEW},
            # The cycles, the module and the intake work item their stories open.
            "cycles": {
                "completed": {"id": str(COMPLETED_CYCLE_ID), "name": Command.COMPLETED_CYCLE},
                "draft": {"id": str(DRAFT_CYCLE_ID), "name": Command.DRAFT_CYCLE},
            },
            "module": {"id": str(MODULE_ID), "name": Command.MODULE},
            "intake": {"id": str(INTAKE_WORK_ITEM_ID), "name": Command.INTAKE_WORK_ITEM},
            "invitations": [email for email, _ in Command.INVITATIONS],
            "sharedLinks": {
                "visible": [t for t, _, hidden in Command.SHARED_LINKS if not hidden],
                "hidden": [t for t, _, hidden in Command.SHARED_LINKS if hidden],
            },
            "users": {
                "light": {
                    "email": users["light"].email,
                    "sessionCookie": mint_app_session(users["light"]),
                },
                "dark": {
                    "email": users["dark"].email,
                    "sessionCookie": mint_app_session(users["dark"]),
                },
                "admin": {
                    "email": users["admin"].email,
                    "sessionCookie": mint_app_session(users["admin"]),
                    "adminSessionCookie": mint_admin_session(users["admin"], verified=True),
                },
            },
        }

        destination = options["out"]
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Seeded visual fixtures -> {destination}"))

    # ------------------------------------------------------------------
    # the world
    # ------------------------------------------------------------------

    def _users(self) -> dict:
        made = {}
        for key, theme in (("light", "light"), ("dark", "dark"), ("admin", "light")):
            user, _ = User.objects.get_or_create(
                email=f"vr-{key}@hangar.test",
                defaults={
                    "id": USER_IDS[key],
                    "username": f"vr-{key}",
                    "display_name": f"VR {key.title()}",
                    "is_active": True,
                },
            )
            user.set_password("visual-regression")
            user.is_password_autoset = False
            user.save()
            # A signed-in user's theme comes from their stored profile, not from
            # any attribute a test could set: `store-wrapper` applies it on first
            # load and overwrites whatever the markup said. Seeding it is the
            # only deterministic lever.
            # Pinned, because the members table prints it. `date_joined` defaults
            # to real time, so without this the workspace members baseline
            # changes date every single day -- and with `visual-regression` a
            # required check, that would block every merge until somebody
            # re-baselined it.
            User.objects.filter(pk=user.pk).update(date_joined=CLOCK - timedelta(days=30))

            profile, _ = Profile.objects.get_or_create(user=user)
            profile.theme = {"theme": theme}
            # Onboarding is a first-run artifact, and the product tour is a
            # modal over the whole page. It covered the workspace home story
            # entirely -- and note the readiness assertion still passed, because
            # a locator behind an overlay is "visible" as far as Playwright is
            # concerned. Nothing here is testing the tour.
            profile.is_tour_completed = True
            profile.is_onboarded = True
            profile.save(update_fields=["theme", "is_tour_completed", "is_onboarded"])
            made[key] = user

        instance = Instance.objects.first()
        if instance is not None:
            InstanceAdmin.objects.get_or_create(instance=instance, user=made["admin"], defaults={"role": ADMIN})
            # `register_instance` leaves an instance un-set-up, and the web app
            # reads that flag to decide between the first-run wizard and the
            # application proper. Without it every authenticated surface renders
            # "Set up your instance" -- a stable, screenshottable page that has
            # nothing to do with what the story claims to capture.
            instance.is_setup_done = True
            instance.is_signup_screen_visited = True
            # `register_instance` mints this with `secrets.token_hex(12)`, and the
            # console prints it in a field on its General page -- so every fresh
            # database produced a different console baseline. Pinned like every
            # other identifier the interface renders.
            instance.instance_id = INSTANCE_ID
            instance.save(update_fields=["is_setup_done", "is_signup_screen_visited", "instance_id"])
            # `GET /api/instances/` is cached for two hours, so a re-seed against
            # a warm instance keeps serving the pre-seed flags and the app keeps
            # rendering the first-run wizard. Writing the model is not enough.
            invalidate_cache_directly(path="/api/instances/", user=False)
        return made

    def _workspace(self, owner) -> Workspace:
        workspace, _ = Workspace.objects.get_or_create(
            id=WORKSPACE_ID,
            defaults={"name": "Hangar VR", "slug": "hangar-vr", "owner": owner},
        )
        for user, role in ((owner, ADMIN),):
            WorkspaceMember.objects.get_or_create(
                workspace=workspace, member=user, defaults={"role": role, "is_active": True}
            )
        return workspace

    def _project(self, workspace, users) -> Project:
        project, created = Project.objects.get_or_create(
            id=PROJECT_ID,
            defaults={
                "name": "Visual Regression",
                "identifier": "VR",
                "workspace": workspace,
                "created_by": users["admin"],
                "cycle_view": True,
                "module_view": True,
            },
        )
        if created:
            ensure_project_system_types(project)
            State.objects.create(
                name="Backlog", color="#6b7280", group="backlog", project=project, workspace=workspace, sequence=1000
            )
            State.objects.create(
                name="In progress",
                color="#f59e0b",
                group="started",
                project=project,
                workspace=workspace,
                sequence=2000,
            )
            State.objects.create(
                name="Done", color="#16a34a", group="completed", project=project, workspace=workspace, sequence=3000
            )
            Label.objects.create(name="backend", color="#2563eb", project=project, workspace=workspace, sort_order=1)
            Label.objects.create(name="interface", color="#db2777", project=project, workspace=workspace, sort_order=2)

        for index, key in enumerate(("light", "dark", "admin")):
            user = users[key]
            membership, _ = WorkspaceMember.objects.get_or_create(
                workspace=workspace, member=user, defaults={"role": MEMBER, "is_active": True}
            )
            # The members table's "Joining date" column. It does not come from
            # `User.date_joined` -- confirmed against the API, where the member
            # object carries no `joining_date` at all and the row's own
            # `created_at` is what reaches the interface. Pinning `date_joined`
            # therefore fixed nothing, and the baseline still moved every day.
            # Staggered rather than identical: the table sorts on this, and
            # three rows sharing one timestamp leave the order to whatever the
            # database returns.
            WorkspaceMember.objects.filter(pk=membership.pk).update(created_at=CLOCK - timedelta(days=30 + index))
            project_membership, _ = ProjectMember.objects.get_or_create(
                project=project,
                member=user,
                defaults={"workspace": workspace, "role": ADMIN if key == "admin" else MEMBER, "is_active": True},
            )
            # The project members table prints this as the "Joining date", the
            # same way the workspace table prints the row above, so it is pinned
            # and staggered for the same reasons.
            ProjectMember.objects.filter(pk=project_membership.pk).update(created_at=CLOCK - timedelta(days=30 + index))
            self._sidebar_preferences(workspace, user)
        # "Created on" in the project settings and on the project cards; the
        # list sorts on it too, so the three projects keep their seeding order.
        Project.objects.filter(pk=project.pk).update(created_at=CLOCK - timedelta(days=60))
        return project

    # The order the sidebar's personal entries render in, which is otherwise
    # decided by a race.
    #
    # `WorkspaceUserPreferenceViewSet.get` creates these rows lazily on first
    # visit, inside a loop that re-issues a growing `bulk_create` with
    # `ignore_conflicts=True`. Each key's `sort_order` therefore depends on its
    # index in the batch that happened to insert it -- and when several browsers
    # arrive at once, as they do here, different requests win for different keys
    # and the resulting order varies from one fresh database to the next.
    #
    # Seeding them explicitly with the values a single unhurried caller would
    # have produced takes the race out of the picture entirely.
    SIDEBAR_PREFERENCES = (
        ("views", 65535.0, False),
        ("active_cycles", 75535.0, False),
        ("analytics", 85535.0, False),
        ("drafts", 95535.0, True),
        ("your_work", 105535.0, True),
        ("archives", 115535.0, False),
        ("stickies", 125535.0, True),
    )

    def _sidebar_preferences(self, workspace, user) -> None:
        for key, sort_order, is_pinned in self.SIDEBAR_PREFERENCES:
            WorkspaceUserPreference.objects.update_or_create(
                workspace=workspace,
                user=user,
                key=key,
                defaults={"sort_order": sort_order, "is_pinned": is_pinned},
            )

    def _work_items(self, workspace, project, author) -> None:
        if Issue.objects.filter(project=project).exists():
            return
        states = list(State.objects.filter(project=project).order_by("sequence"))
        for index, (name, priority) in enumerate(WORK_ITEMS, start=1):
            issue = Issue.objects.create(
                name=name,
                project=project,
                workspace=workspace,
                state=states[index % len(states)],
                priority=priority,
                created_by=author,
            )
            # `auto_now_add` discards whatever is passed on insert, so the dates
            # the interface renders have to be written afterwards or every
            # baseline drifts with the calendar.
            stamped = CLOCK - timedelta(days=index)
            # The same applies to the work item's number, for a subtler reason.
            # `Issue.save()` derives `sequence_id` from the project's current
            # high-water mark, so seeding over a database that has held issues
            # before starts at VR-9 rather than VR-1 -- and the numbers are
            # rendered down the left of the list. CI seeds a fresh volume and a
            # developer re-seeds a warm one, so without this the two disagree on
            # every baseline showing a work item.
            Issue.objects.filter(pk=issue.pk).update(created_at=stamped, updated_at=stamped, sequence_id=index)
            IssueSequence.objects.filter(issue=issue).update(created_at=stamped, updated_at=stamped, sequence=index)

    # Custom properties on the Task type.
    #
    # One of every kind the interface can render, because the property widget is
    # a switch on `property_type` and a baseline that only exercises text says
    # nothing about the other six. Attached to the system Task type rather than
    # a custom type: the settings screen and the sidebar widget do not care
    # which type owns a property, and a custom type would need its own
    # ProjectIssueType row for no additional coverage.
    PROPERTIES = (
        ("Impact", PropertyTypeChoices.SELECT, ("Blocker", "Major", "Minor")),
        ("Reviewers", PropertyTypeChoices.MULTI_SELECT, ("Design", "Security", "Docs")),
        ("Story points", PropertyTypeChoices.NUMBER, ()),
        ("Needs migration", PropertyTypeChoices.BOOLEAN, ()),
        ("Target date", PropertyTypeChoices.DATE, ()),
        ("Release note", PropertyTypeChoices.TEXT, ()),
    )

    def _work_item_properties(self, workspace, project) -> None:
        task_type = IssueType.objects.filter(workspace=workspace, system_key=IssueType.SystemKey.TASK).first()
        if task_type is None:
            return

        first_issue = Issue.objects.filter(project=project).order_by("sequence_id").first()
        if first_issue is not None:
            Issue.objects.filter(pk=first_issue.pk).update(type=task_type)

        for index, (name, kind, options) in enumerate(self.PROPERTIES):
            prop, _ = IssueProperty.objects.update_or_create(
                workspace=workspace,
                issue_type=task_type,
                display_name=name,
                defaults={
                    "property_type": kind,
                    "is_multi": kind == PropertyTypeChoices.MULTI_SELECT,
                    "is_active": True,
                    # Distinct and explicit: the settings screen lists these in
                    # sort order, and equal values would leave the order to
                    # whatever the database felt like returning.
                    "sort_order": 10000.0 * (index + 1),
                },
            )
            for option_index, option in enumerate(options):
                IssuePropertyOption.objects.update_or_create(
                    workspace=workspace,
                    property=prop,
                    name=option,
                    defaults={"sort_order": 10000.0 * (option_index + 1), "is_active": True},
                )

            if first_issue is None:
                continue
            value = {
                PropertyTypeChoices.NUMBER: {"value_number": 8},
                PropertyTypeChoices.BOOLEAN: {"value_boolean": True},
                PropertyTypeChoices.TEXT: {"value_text": "Copying a project now carries its work items."},
                PropertyTypeChoices.DATE: {"value_date": CLOCK + timedelta(days=14)},
            }.get(kind)
            if kind == PropertyTypeChoices.SELECT and options:
                value = {"value_option": prop.options.order_by("sort_order").first()}
            if value:
                IssuePropertyValue.objects.update_or_create(
                    workspace=workspace,
                    project=project,
                    issue=first_issue,
                    property=prop,
                    defaults=value,
                )

    def _worklogs(self, workspace, project, author) -> None:
        """Time tracking, which is off by default and hides the whole widget."""
        Project.objects.filter(pk=project.pk).update(is_time_tracking_enabled=True)

        issue = Issue.objects.filter(project=project).order_by("sequence_id").first()
        if issue is None:
            return
        for index, (minutes, description) in enumerate(
            ((90, "Traced the failing request"), (45, "Wrote the regression test")), start=1
        ):
            worklog, _ = IssueWorkLog.objects.update_or_create(
                workspace=workspace,
                project=project,
                issue=issue,
                logged_by=author,
                description=description,
                defaults={"duration": minutes},
            )
            # The activity feed prints when each entry was logged, relative to
            # the browser's clock, so the real insert time would drift by a day
            # every day.
            logged_at = CLOCK - timedelta(hours=4 - index)
            IssueWorkLog.objects.filter(pk=worklog.pk).update(created_at=logged_at, updated_at=logged_at)
            # The feed lists a worklog through the activity row the worklog view
            # writes (`create_worklog_activity`), which a direct insert skips.
            activity, _ = IssueActivity.objects.get_or_create(
                workspace=workspace,
                project=project,
                issue=issue,
                actor=author,
                field="worklog",
                verb="created",
                new_value=_format_worklog_duration(minutes),
                defaults={"comment": "logged time", "epoch": logged_at.timestamp()},
            )
            IssueActivity.objects.filter(pk=activity.pk).update(created_at=logged_at, updated_at=logged_at)

    COMMENT = "Reproduced on a fresh workspace: the export stalls after the first page."

    def _comments(self, workspace, project, author) -> None:
        """One comment on the first work item, so the activity feed photographs a comment card."""
        issue = Issue.objects.filter(project=project).order_by("sequence_id").first()
        if issue is None:
            return
        comment = IssueComment.objects.filter(issue=issue, actor=author).first()
        if comment is None:
            comment = IssueComment.objects.create(
                workspace=workspace,
                project=project,
                issue=issue,
                actor=author,
                created_by=author,
                comment_html=f"<p>{self.COMMENT}</p>",
            )
        # Printed relative to the browser's clock, like the worklogs above.
        IssueComment.objects.filter(pk=comment.pk).update(
            created_at=CLOCK - timedelta(hours=1), updated_at=CLOCK - timedelta(hours=1)
        )

    # Two visible and one hidden. The widget renders a "show hidden (n)"
    # affordance only when something is hidden, so a seed with three visible
    # links would photograph a different component.
    SHARED_LINKS = (
        ("Runbook", "https://example.invalid/runbook", False),
        ("On-call rota", "https://example.invalid/on-call", False),
        ("Archived wiki", "https://example.invalid/wiki", True),
    )

    PROJECT_VIEW = "Urgent and high"
    WORKSPACE_VIEW = "Everything in review"

    def _views(self, workspace, project, owner) -> None:
        """One public saved view in the project and one in the workspace.

        Without them both view lists render their empty state, and the list
        rows, their access icon and their quick actions show nowhere. The
        filters are left empty: a list row does not print them, and the view's
        own page is the work item layout the layout stories already cover.
        """
        for view_id, name, view_project in (
            (PROJECT_VIEW_ID, Command.PROJECT_VIEW, project),
            (WORKSPACE_VIEW_ID, Command.WORKSPACE_VIEW, None),
        ):
            view, _ = IssueView.objects.get_or_create(
                id=view_id,
                defaults={
                    "name": name,
                    "workspace": workspace,
                    "project": view_project,
                    "owned_by": owner,
                    "created_by": owner,
                    "filters": {},
                    "access": 1,
                },
            )
            # `auto_now_add`, as with the work items: the list rows print no
            # date today, but a row that ever does should not drift.
            IssueView.objects.filter(pk=view.pk).update(
                created_at=CLOCK - timedelta(days=3), updated_at=CLOCK - timedelta(days=3)
            )

    COMPLETED_CYCLE = "Hardening sprint"
    DRAFT_CYCLE = "Next sprint"
    MODULE = "Export overhaul"

    def _cycles_and_modules(self, workspace, project, owner) -> None:
        """Two cycles and one module, none holding work items.

        A cycle that ended before `CLOCK` is completed on the server's clock
        and on the browser's alike, whenever the suite runs; a cycle without
        dates is a draft on both. An active or upcoming cycle would be decided
        by the server's real clock and change status as the calendar moves.
        Neither cycle nor the module holds work items: the work item rows
        print their cycle and module, so membership would move every layout
        baseline.
        """
        for cycle_id, name, start, end, sort_order in (
            (COMPLETED_CYCLE_ID, Command.COMPLETED_CYCLE, CLOCK - timedelta(days=21), CLOCK - timedelta(days=8), 1000),
            (DRAFT_CYCLE_ID, Command.DRAFT_CYCLE, None, None, 2000),
        ):
            cycle, _ = Cycle.objects.get_or_create(
                id=cycle_id,
                defaults={
                    "name": name,
                    "workspace": workspace,
                    "project": project,
                    "owned_by": owner,
                    "created_by": owner,
                    "start_date": start,
                    "end_date": end,
                    "sort_order": sort_order,
                },
            )
            Cycle.objects.filter(pk=cycle.pk).update(
                created_at=CLOCK - timedelta(days=30), updated_at=CLOCK - timedelta(days=30)
            )
        module, _ = Module.objects.get_or_create(
            id=MODULE_ID,
            defaults={
                "name": Command.MODULE,
                "workspace": workspace,
                "project": project,
                "lead": owner,
                "status": "in-progress",
                "start_date": (CLOCK - timedelta(days=10)).date(),
                "target_date": (CLOCK + timedelta(days=20)).date(),
                "created_by": owner,
            },
        )
        Module.objects.filter(pk=module.pk).update(
            created_at=CLOCK - timedelta(days=30), updated_at=CLOCK - timedelta(days=30)
        )

    INTAKE_WORK_ITEM = "Support SAML sign-in for contractors"

    def _intake(self, workspace, project, author) -> None:
        """One pending intake work item, so the intake list and detail show it.

        The project's intake feature stays off: switching it on would add
        "Intake" to the project's sidebar entry in every story, so the intake
        stories patch the flag on the project responses, as the view stories
        do. The work item sits in the triage state, which every work item
        list leaves out, and is numbered after the seeded work items.
        """
        intake, _ = Intake.objects.get_or_create(
            id=INTAKE_ID,
            defaults={
                "name": f"{project.name} Intake",
                "workspace": workspace,
                "project": project,
                "is_default": True,
            },
        )
        triage, _ = State.all_state_objects.get_or_create(
            id=INTAKE_STATE_ID,
            defaults={
                "name": "Triage",
                "group": "triage",
                "color": "#4E5355",
                "sequence": 65000,
                "project": project,
                "workspace": workspace,
            },
        )
        issue = Issue.all_objects.filter(id=INTAKE_WORK_ITEM_ID).first()
        if issue is None:
            issue = Issue.objects.create(
                id=INTAKE_WORK_ITEM_ID,
                name=Command.INTAKE_WORK_ITEM,
                project=project,
                workspace=workspace,
                state=triage,
                priority="medium",
                created_by=author,
            )
        stamped = CLOCK - timedelta(days=2)
        sequence = len(WORK_ITEMS) + 1
        Issue.all_objects.filter(pk=issue.pk).update(created_at=stamped, updated_at=stamped, sequence_id=sequence)
        IssueSequence.objects.filter(issue=issue).update(created_at=stamped, updated_at=stamped, sequence=sequence)
        intake_issue, _ = IntakeIssue.objects.get_or_create(
            id=INTAKE_ISSUE_ID,
            defaults={
                "intake": intake,
                "issue": issue,
                "project": project,
                "workspace": workspace,
                "source": "IN_APP",
                "created_by": author,
            },
        )
        IntakeIssue.objects.filter(pk=intake_issue.pk).update(created_at=stamped, updated_at=stamped)

    def _shared_links(self, workspace, users) -> None:
        for index, (title, url, hidden) in enumerate(self.SHARED_LINKS):
            link, _ = WorkspaceSharedLink.objects.update_or_create(
                workspace=workspace,
                title=title,
                defaults={"url": url, "sort_order": 10000.0 * (index + 1)},
            )
            if hidden:
                WorkspaceSharedLinkHide.objects.update_or_create(
                    workspace=workspace, user=users["light"], shared_link=link
                )

    # Two finished imports, and deliberately no running one.
    #
    # An active job makes the history poll every three seconds and renders a
    # spinning loader; terminal rows give a completely static DOM and still show
    # every part of the row worth photographing -- the status icon, the task
    # tallies, the retry action on a failure and the report link on both.
    #
    # `ImportJob` is fussier than most of what this seed writes. Both digests are
    # CHECK-constrained to 64 hex characters, and a terminal status must have
    # `completed_at` set with the lease fields NULL, so these are not values that
    # can be left to defaults.
    IMPORTS = (
        (
            "completed",
            "0" * 64,
            {"planned_tasks": 128, "imported_tasks": 120, "reused_tasks": 8},
            "",
        ),
        (
            "failed",
            "1" * 64,
            {"planned_tasks": 64, "imported_tasks": 41, "reused_tasks": 0},
            "row_limit_exceeded",
        ),
    )

    def _import_jobs(self, workspace, project, actor) -> None:
        for index, (status, digest, stats, reason) in enumerate(self.IMPORTS, start=1):
            stamped = CLOCK - timedelta(days=index)
            job, _ = ImportJob.objects.update_or_create(
                workspace=workspace,
                project=project,
                source_digest=digest,
                defaults={
                    "provider": ImportJob.Provider.TODOIST_CSV,
                    "status": status,
                    "manifest_digest": digest,
                    "stats": stats,
                    "reason": reason,
                    "initiated_by": actor,
                    "completed_at": stamped,
                    "queued_at": stamped,
                    "started_at": stamped,
                    "lease_token": None,
                    "lease_expires_at": None,
                },
            )
            # `created_at` is auto_now_add and the history orders by it, so the
            # row order is otherwise whatever the insert happened to produce.
            ImportJob.objects.filter(pk=job.pk).update(created_at=stamped, updated_at=stamped)

    # Invitations that have been sent and not yet answered. "Pending" is not a
    # stored state: the endpoint returns every invite that has not been revoked
    # and the interface labels each row unconditionally.
    INVITATIONS = (
        ("invited-admin@hangar.test", ADMIN),
        ("invited-member@hangar.test", MEMBER),
    )

    def _invitations(self, workspace, actor) -> None:
        for index, (email, role) in enumerate(self.INVITATIONS, start=1):
            stamped = CLOCK - timedelta(days=index)
            invite, _ = WorkspaceMemberInvite.objects.update_or_create(
                workspace=workspace,
                email=email,
                defaults={
                    "role": role,
                    "accepted": False,
                    "responded_at": None,
                    # Fixed rather than random: it is not rendered, but a seed
                    # that mints a value per run invites somebody to render it.
                    "token": f"vr-invite-token-{index:02d}",
                    "expires_at": CLOCK + timedelta(days=7),
                    "created_by": actor,
                },
            )
            WorkspaceMemberInvite.objects.filter(pk=invite.pk).update(created_at=stamped, updated_at=stamped)

    def _trainers(self, workspace, project, users) -> list:
        """Trainer profiles, and the Workshop type they unlock.

        Capacity is opt-in by design: `ensure_project_system_types` only adds the
        Workshop work item type once a workspace has a trainer profile, and the
        profile only appears when somebody opts in. So the ledger, the planner
        and the workshop session editor are all downstream of these two rows --
        without them those three surfaces render nothing worth photographing.

        The weekly schedule is left at the model default: it is already a fixed
        weekday window, not anything derived from "today". That matters because
        the ledger draws a timeline against it, and hours that moved with the
        wall clock would be exactly the baseline that passes on the day it is
        recorded and breaks the next morning.
        """
        from plane.ext.models import TrainerProfile
        from plane.ext.services.issue_types import ensure_project_workshop_type

        profiles = []
        for key in ("light", "dark"):
            # `weekly_schedule` is left at the model default, which is already a
            # fixed weekday window rather than anything derived from today. A
            # schedule restated here would be a second copy to keep in step for
            # no gain.
            profile, _ = TrainerProfile.objects.update_or_create(
                workspace=workspace,
                user=users[key],
                defaults={"id": TRAINER_PROFILE_IDS[key], "status": "active", "timezone": "UTC"},
            )
            profiles.append(profile)

        ensure_project_workshop_type(project)
        return profiles

    def _workshop(self, workspace, project, users) -> "Issue":
        """One Workshop work item with three sessions.

        Three rather than one because the session editor's failure mode was a
        layout that only showed up with more than one -- it used to render seven
        stacked rows per session in a sidebar too narrow for any of them.
        """
        from plane.db.models import IssueAssignee
        from plane.ext.models import WorkshopSchedule, WorkshopSession
        from plane.ext.services.issue_types import ensure_project_workshop_type

        workshop_type = ensure_project_workshop_type(project)
        state = State.objects.filter(project=project).order_by("sequence").first()
        issue = Issue.objects.create(
            id=WORKSHOP_ISSUE_ID,
            name="Network security workshop",
            project=project,
            workspace=workspace,
            state=state,
            type=workshop_type,
            created_by=users["admin"],
            sequence_id=len(WORK_ITEMS) + 2,
        )
        Issue.objects.filter(pk=issue.pk).update(created_at=CLOCK, updated_at=CLOCK)

        trainers = [users["light"], users["dark"]]
        for key in ("light", "dark"):
            IssueAssignee.objects.create(
                id=ASSIGNEE_IDS[key],
                issue=issue,
                assignee=users[key],
                project=project,
                workspace=workspace,
            )

        first = CLOCK.replace(hour=9, minute=0) + timedelta(days=1)
        schedule = WorkshopSchedule.objects.create(
            issue=issue,
            workspace=workspace,
            project=project,
            starts_at=first,
            ends_at=first + timedelta(hours=4),
            preparation_minutes=30,
            travel_before_minutes=60,
            travel_after_minutes=45,
        )
        for position in range(3):
            starts_at = first + timedelta(days=position)
            session = WorkshopSession.objects.create(
                schedule=schedule,
                position=position,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=4),
                preparation_minutes=30,
                travel_before_minutes=60,
                travel_after_minutes=45,
            )
            session.trainers.add(*[trainer.id for trainer in trainers])
        return issue

    def _maintenance_notice(self) -> None:
        """An active notice, deliberately with no scheduled window.

        The browser's clock is frozen to CLOCK, but the *server* decides whether
        a notice is active and it uses its own real time -- so a window anchored
        to a fixed past date is permanently expired and the bar never renders.
        Anchoring it to real time instead would make the times the bar prints
        change with the calendar, which is the other way to lose a baseline.

        With no window the bar shows only its message, which is stable, and
        nothing about what is being screenshotted is lost.
        """
        InstanceMaintenanceNotice.objects.all().delete(soft=False)
        InstanceMaintenanceNotice.objects.create(
            is_enabled=True,
            severity=InstanceMaintenanceNotice.Severity.WARNING,
            message="Maintenance 22:00-22:30 today. Hangar will be briefly unavailable.",
            starts_at=None,
            ends_at=None,
            show_on_sign_in=True,
        )

    def _copy_in_flight(self, workspace, source, users) -> Project:
        """A copy frozen mid-flight, for the progress strip.

        `status="processing"` is refused by a check constraint unless the lease
        and start time are set, so this is not simply a status field.
        """
        target, _ = Project.objects.get_or_create(
            id=COPY_TARGET_ID,
            defaults={
                "name": "Visual Regression (Copy)",
                "identifier": "VRC",
                "workspace": workspace,
                "created_by": users["admin"],
            },
        )
        # Everybody, not just whoever started the copy. The progress strip only
        # renders for a member of the project being copied into, so seeding one
        # member means the story can only ever be told as that user -- and the
        # copy-status endpoint answers a non-member with a permission error,
        # which reaches the interface as no strip at all.
        for key, user in users.items():
            ProjectMember.objects.get_or_create(
                project=target,
                member=user,
                defaults={
                    "workspace": workspace,
                    "role": ADMIN if key == "admin" else MEMBER,
                    "is_active": True,
                },
            )
        Project.objects.filter(pk=target.pk).update(created_at=CLOCK - timedelta(days=59))
        # Hard delete: `target_project` is a OneToOne, so its unique index is
        # unconditional and a soft-deleted row keeps occupying it -- re-seeding
        # would fail on a constraint the row is no longer logically part of.
        ProjectCopyJob.objects.filter(target_project=target).delete(soft=False)
        ProjectCopyJob.objects.create(
            workspace=workspace,
            source_project=source,
            target_project=target,
            initiated_by=users["admin"],
            status=ProjectCopyJob.Status.PROCESSING,
            stage=ProjectCopyJob.Stage.ISSUES,
            total=40,
            copied=12,
            lease_token=uuid.UUID("a0000000-0000-4000-8000-0000000000ff"),
            lease_expires_at=CLOCK + timedelta(minutes=5),
            started_at=CLOCK,
        )
        return target

    # The work items on the published board: name, priority, label names, and
    # the due date as days from CLOCK (None for none). Overdue, due today and
    # due later each colour the date differently; one carries both labels so
    # the chip shows a count.
    PUBLISHED_WORK_ITEMS = (
        ("Publish the release notes", "urgent", ("release",), -2),
        ("Check the public roadmap", "high", ("docs", "release"), 0),
        ("Answer the board comments", "medium", ("docs",), 5),
        ("Tidy the changelog", "none", (), None),
    )

    def _published_board(self, workspace, owner) -> DeployBoard:
        """A project published to the web, for the space stories.

        No `ProjectMember` rows, and secret: the signed-in stories photograph
        sidebars and project lists, and a project nobody belongs to appears in
        none of them. Its work items have no assignees, so the board does not
        depend on which properties it shows to prove anything about them; the
        visibility decision is `apps/space/helpers/display-properties.helper.ts`.
        """
        project, created = Project.objects.get_or_create(
            id=PUBLISHED_PROJECT_ID,
            defaults={
                "name": "Published board",
                "identifier": "PUB",
                "workspace": workspace,
                "created_by": owner,
                "network": 0,
            },
        )
        # The admin's projects list shows this card too ("Join"), with its date.
        Project.objects.filter(pk=project.pk).update(created_at=CLOCK - timedelta(days=58))
        if created:
            ensure_project_system_types(project)
            states = [
                State.objects.create(
                    name=name, color=color, group=group, project=project, workspace=workspace, sequence=sequence
                )
                for name, color, group, sequence in (
                    ("Backlog", "#6b7280", "backlog", 1000),
                    ("In progress", "#f59e0b", "started", 2000),
                    ("Done", "#16a34a", "completed", 3000),
                )
            ]
            labels = {
                name: Label.objects.create(
                    id=PUBLISHED_LABEL_IDS[name],
                    name=name,
                    color=color,
                    project=project,
                    workspace=workspace,
                    sort_order=index,
                )
                for index, (name, color) in enumerate((("docs", "#2563eb"), ("release", "#db2777")), start=1)
            }
            for index, (name, priority, label_names, due_in) in enumerate(Command.PUBLISHED_WORK_ITEMS, start=1):
                issue = Issue.objects.create(
                    name=name,
                    project=project,
                    workspace=workspace,
                    state=states[(index - 1) % 2],
                    priority=priority,
                    target_date=None if due_in is None else (CLOCK + timedelta(days=due_in)).date(),
                    created_by=owner,
                )
                stamped = CLOCK - timedelta(days=index)
                Issue.objects.filter(pk=issue.pk).update(created_at=stamped, updated_at=stamped, sequence_id=index)
                IssueSequence.objects.filter(issue=issue).update(created_at=stamped, updated_at=stamped, sequence=index)
                for label_name in label_names:
                    IssueLabel.objects.create(
                        issue=issue, label=labels[label_name], project=project, workspace=workspace
                    )
        board, _ = DeployBoard.objects.get_or_create(
            entity_name="project",
            entity_identifier=project.id,
            defaults={
                "project": project,
                "workspace": workspace,
                "anchor": PUBLISHED_ANCHOR,
                "view_props": {"list": True, "kanban": True},
                "is_comments_enabled": True,
                "is_reactions_enabled": True,
                "is_votes_enabled": True,
            },
        )
        return board
