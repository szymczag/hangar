# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations
from django.utils import timezone


def spend_invitations_already_honoured(apps, schema_editor):
    """Retire invitations to workspaces their recipient already belongs to.

    Written out here rather than calling the runtime helper: a migration has to
    keep working when that helper changes, and this one describes the state of
    the data at this point in time.

    Only invitations whose address is an active member of the very workspace
    they name are touched. Those have nothing left to offer, and left
    outstanding they are a way back in after the person is removed.
    """
    WorkspaceMemberInvite = apps.get_model("db", "WorkspaceMemberInvite")
    WorkspaceMember = apps.get_model("db", "WorkspaceMember")

    now = timezone.now()
    outstanding = WorkspaceMemberInvite.objects.filter(consumed_at__isnull=True, deleted_at__isnull=True)

    spent = []
    for invite in outstanding.iterator(chunk_size=500):
        if WorkspaceMember.objects.filter(
            workspace_id=invite.workspace_id,
            member__email__iexact=invite.email,
            is_active=True,
        ).exists():
            spent.append(invite.pk)

    for start in range(0, len(spent), 500):
        WorkspaceMemberInvite.objects.filter(pk__in=spent[start : start + 500]).update(consumed_at=now, deleted_at=now)


class Migration(migrations.Migration):
    dependencies = [("db", "0129_alter_draftissue_assignees_alter_issue_assignees_and_more")]
    operations = [migrations.RunPython(spend_invitations_already_honoured, migrations.RunPython.noop)]
