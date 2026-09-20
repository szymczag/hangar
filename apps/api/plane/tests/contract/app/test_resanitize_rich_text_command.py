# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""The one-off command that brings stored rich text under the current allowlist."""

from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command

from plane.db.models import Issue, IssueComment, Project, State
from plane.db.management.commands.resanitize_rich_text import classify

HOSTILE = '<p><span data-text-color="red;position:fixed;inset:0">x</span><img src=x onerror=alert(1)></p>'
CLEAN = '<p class="editor-paragraph-block"><span data-text-color="gray">x</span></p>'


@pytest.fixture
def issue(db, workspace, create_user):
    project = Project.objects.create(name="Resanitize", identifier=f"R{uuid4().hex[:4]}", workspace=workspace)
    state = State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)
    return Issue.objects.create(
        name="Stored before the allowlist", workspace=workspace, project=project, state=state, created_by=create_user
    )


def run(*args):
    out = StringIO()
    call_command("resanitize_rich_text", *args, stdout=out)
    return out.getvalue()


@pytest.mark.unit
def test_classify_separates_removals_from_serialization():
    sanitized, affected = classify(HOSTILE)
    assert affected
    assert "onerror" not in sanitized and "position" not in sanitized
    assert classify(CLEAN) == (CLEAN, False)


@pytest.mark.contract
@pytest.mark.django_db
def test_report_writes_nothing_and_apply_rewrites(issue, create_user):
    # Written with update() to bypass the serializers, as old rows were.
    Issue.objects.filter(pk=issue.pk).update(description_html=HOSTILE)
    comment = IssueComment.objects.create(
        issue=issue,
        project=issue.project,
        workspace=issue.workspace,
        comment_html=CLEAN,
        actor=create_user,
        created_by=create_user,
    )

    report = run()
    assert "Issue.description_html: scanned" in report
    assert "affected 1" in report
    assert str(issue.pk) in report
    issue.refresh_from_db()
    assert issue.description_html == HOSTILE

    run("--apply")
    issue.refresh_from_db()
    comment.refresh_from_db()
    assert "onerror" not in issue.description_html
    assert "position" not in issue.description_html
    assert comment.comment_html == CLEAN

    assert "0 row(s) would be rewritten" in run()
