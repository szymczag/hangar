# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from django.db import migrations, models
from django.db.models import Q


def provision_system_types(apps, schema_editor):
    Issue = apps.get_model("db", "Issue")
    IssueType = apps.get_model("db", "IssueType")
    Project = apps.get_model("db", "Project")
    ProjectIssueType = apps.get_model("db", "ProjectIssueType")

    projects = Project.objects.filter(deleted_at__isnull=True).only("id", "workspace_id")
    for project in projects.iterator():
        epic_type = (
            IssueType.objects.filter(
                workspace_id=project.workspace_id,
                system_key="epic",
                deleted_at__isnull=True,
            )
            .order_by("created_at")
            .first()
        )
        if epic_type is None:
            epic_type = (
                IssueType.objects.filter(
                    workspace_id=project.workspace_id,
                    is_epic=True,
                    deleted_at__isnull=True,
                )
                .order_by("created_at")
                .first()
            )
        if epic_type is None:
            epic_type = IssueType.objects.create(
                workspace_id=project.workspace_id,
                name="Epic",
                is_epic=True,
                is_active=True,
                level=1,
                system_key="epic",
            )
        elif (
            epic_type.system_key != "epic"
            or epic_type.level != 1
            or not epic_type.is_epic
            or not epic_type.is_active
            or epic_type.is_default
        ):
            epic_type.system_key = "epic"
            epic_type.level = 1
            epic_type.is_epic = True
            epic_type.is_active = True
            epic_type.is_default = False
            epic_type.save(update_fields=["system_key", "level", "is_epic", "is_active", "is_default"])

        task_type = (
            IssueType.objects.filter(
                workspace_id=project.workspace_id,
                system_key="task",
                deleted_at__isnull=True,
            )
            .order_by("created_at")
            .first()
        )
        if task_type is None:
            task_type = IssueType.objects.create(
                workspace_id=project.workspace_id,
                name="Task",
                is_epic=False,
                is_active=True,
                is_default=True,
                level=0,
                system_key="task",
            )
        elif (
            task_type.system_key != "task"
            or task_type.level != 0
            or task_type.is_epic
            or not task_type.is_active
            or not task_type.is_default
        ):
            task_type.system_key = "task"
            task_type.level = 0
            task_type.is_epic = False
            task_type.is_active = True
            task_type.is_default = True
            task_type.save(update_fields=["system_key", "level", "is_epic", "is_active", "is_default"])

        epic_link, _ = ProjectIssueType.objects.get_or_create(
            project_id=project.id,
            issue_type_id=epic_type.id,
            deleted_at__isnull=True,
            defaults={"level": 1, "is_default": False, "workspace_id": project.workspace_id},
        )
        if epic_link.level != 1 or epic_link.is_default:
            epic_link.level = 1
            epic_link.is_default = False
            epic_link.save(update_fields=["level", "is_default"])

        task_link, _ = ProjectIssueType.objects.get_or_create(
            project_id=project.id,
            issue_type_id=task_type.id,
            deleted_at__isnull=True,
            defaults={"level": 0, "is_default": True, "workspace_id": project.workspace_id},
        )
        if task_link.level != 0 or not task_link.is_default:
            task_link.level = 0
            task_link.is_default = True
            task_link.save(update_fields=["level", "is_default"])

        ProjectIssueType.objects.filter(project_id=project.id, deleted_at__isnull=True).exclude(id=task_link.id).update(
            is_default=False
        )
        ProjectIssueType.objects.filter(
            project_id=project.id, issue_type__is_epic=True, deleted_at__isnull=True
        ).update(level=1, is_default=False)
        # Issue's custom manager is not serialized into historical migration
        # state. The base manager is always available on the historical model.
        Issue._base_manager.filter(project_id=project.id, type_id__isnull=True, deleted_at__isnull=True).update(
            type_id=task_type.id
        )


class Migration(migrations.Migration):
    # PostgreSQL cannot build the IssueType partial index while deferred FK
    # trigger events from ProjectIssueType provisioning are pending. Commit the
    # atomic data backfill before applying the constraints.
    atomic = False

    dependencies = [("db", "0126_optional_issue_external_identifiers")]

    operations = [
        migrations.AddField(
            model_name="issuetype",
            name="system_key",
            field=models.CharField(
                blank=True,
                choices=[("task", "Task"), ("epic", "Epic")],
                max_length=32,
                null=True,
            ),
        ),
        migrations.RunPython(provision_system_types, migrations.RunPython.noop, atomic=True),
        migrations.AddConstraint(
            model_name="issuetype",
            constraint=models.UniqueConstraint(
                condition=Q(system_key__isnull=False, deleted_at__isnull=True),
                fields=("workspace", "system_key"),
                name="issue_type_unique_active_system_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="issuetype",
            constraint=models.CheckConstraint(
                check=(
                    Q(system_key__isnull=True)
                    | Q(
                        system_key="epic",
                        is_epic=True,
                        is_active=True,
                        is_default=False,
                        level=1,
                    )
                    | Q(
                        system_key="task",
                        is_epic=False,
                        is_active=True,
                        is_default=True,
                        level=0,
                    )
                ),
                name="issue_type_system_key_invariants",
            ),
        ),
    ]
