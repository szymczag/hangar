# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What a workspace gives its people before they have chosen anything.

None of this could be expressed in the upstream tables. `WorkspaceHomePreference`
is unique on (workspace, user, key) with a non-nullable user, and every read of
`WorkspaceUserLink` filters `owner=request.user`. Making `user` nullable there to
fit a workspace-scoped row would silently change the meaning of every
`filter(user=request.user)` in the codebase, so these are separate tables.

The split between "default" and "shared" is deliberate and is the whole design:

A widget layout is *seeded*. It is a starting point, and the moment someone
rearranges their own home page it is theirs. `WorkspaceDefaultsAdoption` is what
makes "already personalised" distinguishable from "never seen it".

A quick link is *shared*, not copied. Copying loses on the two operations that
actually happen: fix a typo in a URL and every copy still points at the broken
one, with no path to reach them because writes are owner-scoped; retire an
internal service and the dead link survives on forty home pages. So the links
stay one list that everybody reads, and `WorkspaceSharedLinkHide` is how a person
adjusts it without editing something that is not theirs.
"""

# Django imports
from django.conf import settings
from django.db import models

# Module imports
from plane.db.models.base import BaseModel


class WorkspaceHomeDefault(BaseModel):
    """The home-page layout a new member starts with."""

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="home_defaults",
    )
    key = models.CharField(max_length=255)
    is_enabled = models.BooleanField(default=True)
    sort_order = models.FloatField(default=65535)
    config = models.JSONField(default=dict)
    # Bumped when an administrator pushes the defaults over existing members.
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "ext_workspace_home_defaults"
        verbose_name = "Workspace home default"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "key"],
                condition=models.Q(deleted_at__isnull=True),
                name="ext_workspace_home_defaults_unique_workspace_key",
            )
        ]
        ordering = ("sort_order",)

    def __str__(self):
        return f"{self.workspace_id} {self.key}"


class WorkspaceDefaultsAdoption(BaseModel):
    """Which version of the defaults this person's home page was built from.

    Without it there is no way to tell someone who deliberately turned a widget
    off from someone who has simply never opened their home page, and "apply to
    new members only" would have no meaning.
    """

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="home_default_adoptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_home_default_adoptions",
    )
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "ext_workspace_defaults_adoptions"
        verbose_name = "Workspace defaults adoption"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user"],
                condition=models.Q(deleted_at__isnull=True),
                name="ext_workspace_defaults_adoptions_unique_workspace_user",
            )
        ]

    def __str__(self):
        return f"{self.workspace_id} {self.user_id} v{self.version}"


class WorkspaceSharedLink(BaseModel):
    """A quick link the workspace gives everyone, owned by the workspace."""

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="shared_links",
    )
    title = models.CharField(max_length=255, blank=True)
    url = models.TextField()
    metadata = models.JSONField(default=dict)
    sort_order = models.FloatField(default=65535)

    class Meta:
        db_table = "ext_workspace_shared_links"
        verbose_name = "Workspace shared link"
        ordering = ("sort_order", "created_at")

    def __str__(self):
        return f"{self.workspace_id} {self.url}"


class WorkspaceSharedLinkHide(BaseModel):
    """One person choosing not to see one shared link.

    This is what "people can still adjust" means for something they do not own:
    they may hide it from their own home page, and bring it back, without
    touching what anyone else sees.
    """

    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="shared_link_hides",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_shared_link_hides",
    )
    shared_link = models.ForeignKey(
        WorkspaceSharedLink,
        on_delete=models.CASCADE,
        related_name="hides",
    )

    class Meta:
        db_table = "ext_workspace_shared_link_hides"
        verbose_name = "Workspace shared link hide"
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "user", "shared_link"],
                condition=models.Q(deleted_at__isnull=True),
                name="ext_workspace_shared_link_hides_unique",
            )
        ]

    def __str__(self):
        return f"{self.user_id} hid {self.shared_link_id}"
