# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from plane.db.models import Issue, IssueType
from plane.db.models.issue_type import ProjectIssueType


@pytest.mark.contract
@pytest.mark.django_db(transaction=True)
def test_issue_type_migration_upgrades_legacy_projects_without_claiming_custom_task(workspace, request):
    if request.config.getoption("nomigrations") or "django_migrations" not in connection.introspection.table_names():
        pytest.skip("upgrade-path test requires pytest --migrations")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
            ["db", "0127_issue_type_system_keys"],
        )
        if cursor.fetchone() is None:
            pytest.skip("upgrade-path test requires the issue type migration")

    executor = MigrationExecutor(connection)
    executor.migrate([("db", "0126_optional_issue_external_identifiers")])
    legacy_apps = executor.loader.project_state([("db", "0126_optional_issue_external_identifiers")]).apps

    LegacyIssue = legacy_apps.get_model("db", "Issue")
    LegacyIssueType = legacy_apps.get_model("db", "IssueType")
    LegacyProject = legacy_apps.get_model("db", "Project")
    LegacyProjectIssueType = legacy_apps.get_model("db", "ProjectIssueType")

    project = LegacyProject.objects.create(
        workspace_id=workspace.id,
        name="Legacy work items",
        identifier="LWI",
    )
    custom_task = LegacyIssueType.objects.create(workspace_id=workspace.id, name="Task")
    LegacyProjectIssueType.objects.create(
        workspace_id=workspace.id,
        project_id=project.id,
        issue_type_id=custom_task.id,
    )
    # Issue's custom manager is intentionally not serialized into historical
    # migration state, so use Django's automatically provided base manager.
    untyped_issue = LegacyIssue._base_manager.create(
        workspace_id=workspace.id,
        project_id=project.id,
        name="Untyped legacy work item",
    )

    try:
        executor = MigrationExecutor(connection)
        executor.migrate([("db", "0127_issue_type_system_keys")])

        custom_task_after = IssueType.objects.get(pk=custom_task.id)
        canonical_task = IssueType.objects.get(workspace_id=workspace.id, system_key=IssueType.SystemKey.TASK)
        canonical_epic = IssueType.objects.get(workspace_id=workspace.id, system_key=IssueType.SystemKey.EPIC)

        assert custom_task_after.system_key is None
        assert custom_task_after.id != canonical_task.id
        assert Issue.objects.get(pk=untyped_issue.id).type_id == canonical_task.id
        assert ProjectIssueType.objects.filter(
            project_id=project.id,
            issue_type=canonical_task,
            is_default=True,
            level=0,
        ).exists()
        assert ProjectIssueType.objects.filter(
            project_id=project.id,
            issue_type=canonical_epic,
            is_default=False,
            level=1,
        ).exists()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes("db"))
