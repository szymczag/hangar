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
    Issue,
    IssueSequence,
    Label,
    Profile,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceUserPreference,
)
from plane.ext.auth.sessions import mint_admin_session, mint_app_session
from plane.ext.models import InstanceMaintenanceNotice, ProjectCopyJob
from plane.ext.services.issue_types import ensure_project_system_types
from plane.license.models import InstanceAdmin, Instance
from plane.utils.cache import invalidate_cache_directly

# The one instant everything is anchored to. Handed to the browser as well, so a
# relative timestamp rendered in the interface is stable rather than a slow leak
# that fails the suite on a schedule.
CLOCK = datetime(2026, 1, 15, 12, 0, 0, tzinfo=dt_timezone.utc)

ADMIN, MEMBER = 20, 15

WORKSPACE_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
PROJECT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000002")
COPY_TARGET_ID = uuid.UUID("a0000000-0000-4000-8000-000000000003")
# 24 hex characters, the shape `secrets.token_hex(12)` produces.
INSTANCE_ID = "a00000000000400080000000"

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
        self._maintenance_notice()
        copy_target = self._copy_in_flight(workspace, project, users)

        manifest = {
            "clock": CLOCK.isoformat().replace("+00:00", "Z"),
            "workspace": {"slug": workspace.slug, "id": str(workspace.id)},
            "project": {"id": str(project.id), "identifier": project.identifier},
            "copyTarget": {"id": str(copy_target.id)},
            # Published so a spec can wait on real seeded content rather than on
            # a string typed into the spec, which drifts from the seed silently.
            "workItems": [name for name, _ in WORK_ITEMS],
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
                defaults={"username": f"vr-{key}", "display_name": f"VR {key.title()}", "is_active": True},
            )
            user.set_password("visual-regression")
            user.is_password_autoset = False
            user.save()
            # A signed-in user's theme comes from their stored profile, not from
            # any attribute a test could set: `store-wrapper` applies it on first
            # load and overwrites whatever the markup said. Seeding it is the
            # only deterministic lever.
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.theme = {"theme": theme}
            profile.save(update_fields=["theme"])
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

        for key in ("light", "dark", "admin"):
            user = users[key]
            WorkspaceMember.objects.get_or_create(
                workspace=workspace, member=user, defaults={"role": MEMBER, "is_active": True}
            )
            ProjectMember.objects.get_or_create(
                project=project,
                member=user,
                defaults={"workspace": workspace, "role": ADMIN if key == "admin" else MEMBER, "is_active": True},
            )
            self._sidebar_preferences(workspace, user)
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
