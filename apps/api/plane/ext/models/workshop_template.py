# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from plane.db.models.base import BaseModel

MAX_TEMPLATES_PER_WORKSPACE = 20
MAX_ITEMS_PER_TEMPLATE = 30
MAX_OFFSET_DAYS = 365
MAX_ROLES_PER_WORKSPACE = 30
MAX_MEMBERS_PER_ROLE = 25


class WorkshopRole(BaseModel):
    """A standing job in running a workshop, and whoever currently does it.

    A checklist item that names a person goes stale the moment that person
    changes team, and fixing it means editing every template that mentions them.
    A role is named after the work -- streaming, feedback, materials -- so the
    template says what has to happen and this says who does it today. Rotation
    is then one edit here, and no template changes at all.

    Deliberately not the dormant upstream `db.Team`: that table has no
    membership model, no endpoints and no screen, so there is nothing to reuse
    and reviving it would tie this to a shape upstream may yet define.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_roles")
    name = models.CharField(max_length=80)
    # `through_fields` is required, not decorative: `BaseModel` gives the through
    # model its own `created_by`/`updated_by` links to the user, so without this
    # Django cannot tell which foreign key carries the membership.
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ext.WorkshopRoleMember",
        through_fields=("role", "member"),
        related_name="workshop_roles",
    )

    class Meta:
        db_table = "ext_workshop_roles"
        verbose_name = "Workshop role"
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=Q(deleted_at__isnull=True),
                name="ext_workshop_role_unique_name",
            )
        ]

    def __str__(self):
        return f"{self.workspace_id} {self.name}"


class WorkshopRoleMember(BaseModel):
    role = models.ForeignKey(WorkshopRole, on_delete=models.CASCADE, related_name="memberships")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workshop_role_seats")

    class Meta:
        db_table = "ext_workshop_role_members"
        verbose_name = "Workshop role member"
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=["role", "member"],
                condition=Q(deleted_at__isnull=True),
                name="ext_workshop_role_member_unique",
            )
        ]

    def __str__(self):
        return f"{self.role_id} {self.member_id}"


class WorkshopChecklistTemplate(BaseModel):
    """The subtasks a Workshop starts with.

    Workspace-scoped rather than per project, because the checklist follows how
    the organization runs a workshop -- materials, streaming, feedback -- and
    that does not change when the same workshop is filed under a different
    project. `WorkspaceHomeDefault` is the same shape for the same reason.
    """

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_checklist_templates")
    name = models.CharField(max_length=120)
    # At most one per workspace is applied automatically to a new Workshop. The
    # uniqueness of that is enforced by the view, not the database: an operator
    # switching the default should not have to be told the order to do it in.
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "ext_workshop_checklist_templates"
        verbose_name = "Workshop checklist template"
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=Q(deleted_at__isnull=True),
                name="ext_workshop_checklist_template_unique_name",
            )
        ]
        indexes = [models.Index(fields=["workspace", "is_default"], name="ext_wct_ws_default_idx")]

    def __str__(self):
        return f"{self.workspace_id} {self.name}"


class WorkshopChecklistItem(BaseModel):
    """One subtask the template creates."""

    class AssigneeMode(models.TextChoices):
        UNASSIGNED = "unassigned", "Unassigned"
        FIXED = "fixed", "A specific person"
        # Resolved when the template is applied, against the Workshop's own
        # trainers -- which is what "materials, assigned to the trainer" means
        # when the trainer differs from workshop to workshop.
        WORKSHOP_TRAINER = "workshop_trainer", "The workshop's trainer"
        # Resolved against a WorkshopRole's current members, so the template
        # survives the people in it changing.
        ROLE = "role", "Whoever holds a role"

    template = models.ForeignKey(WorkshopChecklistTemplate, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="workshop_checklist_items",
    )
    assignee_mode = models.CharField(max_length=20, choices=AssigneeMode.choices, default=AssigneeMode.UNASSIGNED)
    # SET_NULL rather than CASCADE: losing a role must never take the checklist
    # items that named it down as well. In practice the endpoint releases them
    # itself, because deleting a role is a soft delete and the database therefore
    # never fires this; it stands as the backstop for a hard delete.
    role = models.ForeignKey(
        WorkshopRole,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checklist_items",
    )
    # Relative to the workshop's first session. Negative is before it, which is
    # where preparation work belongs; positive is after, for follow-up.
    offset_days = models.IntegerField(
        default=0,
        validators=[MinValueValidator(-MAX_OFFSET_DAYS), MaxValueValidator(MAX_OFFSET_DAYS)],
    )

    class Meta:
        db_table = "ext_workshop_checklist_items"
        verbose_name = "Workshop checklist item"
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(fields=["template", "position"], name="ext_workshop_checklist_item_position"),
            models.CheckConstraint(
                condition=Q(offset_days__gte=-MAX_OFFSET_DAYS, offset_days__lte=MAX_OFFSET_DAYS),
                name="ext_workshop_checklist_item_offset_range",
            ),
            models.CheckConstraint(
                condition=~Q(assignee_mode="fixed") | Q(assignee__isnull=False),
                name="ext_workshop_checklist_item_fixed_needs_assignee",
            ),
            models.CheckConstraint(
                condition=~Q(assignee_mode="role") | Q(role__isnull=False),
                name="ext_workshop_checklist_item_role_needs_role",
            ),
        ]

    def __str__(self):
        return f"{self.template_id} {self.position} {self.title}"


class WorkshopChecklistOrigin(BaseModel):
    """Which template item a Workshop subtask came from, and its date offset.

    Load-bearing rather than bookkeeping. A Workshop work item exists before it
    has a date -- `WorkshopSchedule` is only created when the planner books a
    session -- so a subtask created at the same time as the Workshop cannot yet
    know its own due date. Keeping the offset here is what lets scheduling fill
    those dates in afterwards; without it there is nothing to count from.

    The item itself is nullable because a template may be edited or removed long
    after the subtasks it produced were created, and that must not delete work.
    """

    issue = models.OneToOneField("db.Issue", on_delete=models.CASCADE, related_name="checklist_origin")
    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="workshop_checklist_origins")
    item = models.ForeignKey(
        WorkshopChecklistItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_issues",
    )
    offset_days = models.IntegerField(
        validators=[MinValueValidator(-MAX_OFFSET_DAYS), MaxValueValidator(MAX_OFFSET_DAYS)]
    )

    class Meta:
        db_table = "ext_workshop_checklist_origins"
        verbose_name = "Workshop checklist origin"
        indexes = [models.Index(fields=["workspace"], name="ext_wco_ws_idx")]

    def __str__(self):
        return f"{self.issue_id} {self.offset_days}"
