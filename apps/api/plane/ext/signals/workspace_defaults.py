# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Give a new member the workspace's home layout before they ask for it.

Upstream's home endpoint lazily creates any missing `WorkspaceHomePreference`
rows with `ignore_conflicts=True`. Rather than edit that loop, this seeds
earlier: by the time a browser first calls the endpoint the rows already exist,
so upstream's loop finds them and leaves them alone. Zero backend edit to
upstream, and every join path -- invitation, SSO auto-join, workspace creation --
is covered by construction, because all of them create a `WorkspaceMember`.
"""

# Django imports
from django.db.models.signals import post_save
from django.dispatch import receiver

# Module imports
from plane.db.models import WorkspaceHomePreference, WorkspaceMember


def apply_home_defaults(workspace_id, user_id):
    """Create this person's home rows from the workspace's defaults.

    Returns the version adopted, or None when the workspace has set no defaults
    -- in which case nothing is written and upstream's own lazy seed still runs,
    which is exactly what a workspace that never configured this wants.
    """
    # Imported here rather than at module scope: this module is loaded from
    # AppConfig.ready(), which runs before the app registry is fully populated.
    from plane.ext.models import WorkspaceDefaultsAdoption, WorkspaceHomeDefault

    defaults = list(WorkspaceHomeDefault.objects.filter(workspace_id=workspace_id, deleted_at__isnull=True))
    if not defaults:
        return None

    version = max(default.version for default in defaults)

    WorkspaceHomePreference.objects.bulk_create(
        [
            WorkspaceHomePreference(
                workspace_id=workspace_id,
                user_id=user_id,
                key=default.key,
                is_enabled=default.is_enabled,
                sort_order=default.sort_order,
                config=default.config,
            )
            for default in defaults
        ],
        batch_size=20,
        # A row this person already has wins. Seeding must never overwrite a
        # choice somebody made.
        ignore_conflicts=True,
    )

    WorkspaceDefaultsAdoption.objects.update_or_create(
        workspace_id=workspace_id,
        user_id=user_id,
        defaults={"version": version},
    )
    return version


@receiver(post_save, sender=WorkspaceMember)
def seed_home_defaults(sender, instance, created, **kwargs):
    if not created:
        return
    apply_home_defaults(instance.workspace_id, instance.member_id)
