# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import migrations, models
from django.db.models import Count, Q


def reject_existing_duplicates(apps, _schema_editor):
    candidates = (
        (apps.get_model("db", "Issue"), ("project_id", "external_source", "external_id")),
        (apps.get_model("db", "IssueComment"), ("issue_id", "external_source", "external_id")),
        (apps.get_model("db", "Module"), ("project_id", "external_source", "external_id")),
    )
    for model, fields in candidates:
        duplicates = (
            model._base_manager.filter(
                deleted_at__isnull=True,
                external_source="todoist_csv",
                external_id__isnull=False,
            )
            .values(*fields)
            .annotate(row_count=Count("id"))
            .filter(row_count__gt=1)
        )
        if duplicates.exists():
            raise RuntimeError(
                f"Cannot add Todoist idempotency index: {model._meta.label} contains duplicate active external IDs"
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("db", "0124_federated_sso_identity"),
    ]

    operations = [
        migrations.RunPython(reject_existing_duplicates, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        CREATE UNIQUE INDEX CONCURRENTLY todoist_issue_external_uidx
                        ON issues (project_id, external_source, external_id)
                        WHERE deleted_at IS NULL
                          AND external_source = 'todoist_csv'
                          AND external_id IS NOT NULL;
                    """,
                    reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS todoist_issue_external_uidx;",
                ),
                migrations.RunSQL(
                    sql="""
                        CREATE UNIQUE INDEX CONCURRENTLY todoist_comment_external_uidx
                        ON issue_comments (issue_id, external_source, external_id)
                        WHERE deleted_at IS NULL
                          AND external_source = 'todoist_csv'
                          AND external_id IS NOT NULL;
                    """,
                    reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS todoist_comment_external_uidx;",
                ),
                migrations.RunSQL(
                    sql="""
                        CREATE UNIQUE INDEX CONCURRENTLY todoist_module_external_uidx
                        ON modules (project_id, external_source, external_id)
                        WHERE deleted_at IS NULL
                          AND external_source = 'todoist_csv'
                          AND external_id IS NOT NULL;
                    """,
                    reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS todoist_module_external_uidx;",
                ),
            ],
            state_operations=[
                migrations.AddConstraint(
                    model_name="issue",
                    constraint=models.UniqueConstraint(
                        fields=("project", "external_source", "external_id"),
                        condition=Q(
                            deleted_at__isnull=True,
                            external_source="todoist_csv",
                            external_id__isnull=False,
                        ),
                        name="todoist_issue_external_uidx",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="issuecomment",
                    constraint=models.UniqueConstraint(
                        fields=("issue", "external_source", "external_id"),
                        condition=Q(
                            deleted_at__isnull=True,
                            external_source="todoist_csv",
                            external_id__isnull=False,
                        ),
                        name="todoist_comment_external_uidx",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="module",
                    constraint=models.UniqueConstraint(
                        fields=("project", "external_source", "external_id"),
                        condition=Q(
                            deleted_at__isnull=True,
                            external_source="todoist_csv",
                            external_id__isnull=False,
                        ),
                        name="todoist_module_external_uidx",
                    ),
                ),
            ],
        ),
    ]
