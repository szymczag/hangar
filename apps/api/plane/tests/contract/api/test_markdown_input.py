# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Markdown accepted on the write surfaces a script uses.

The rendered HTML goes through the same nh3 pass as hand-written HTML, so these
tests care about two things: that the markdown became the markup it should, and
that nothing a caller writes can reach the document as script.
"""

from pathlib import Path

import pytest
from lxml import html as lxml_html
from rest_framework import status

from plane.db.models import Intake, Issue, IssueComment, Project, ProjectMember, State
from plane.ext.services.markdown import MAX_MARKDOWN_SIZE


POLYGLOTS = [
    line
    for line in (Path(__file__).parent / "data" / "xss-polyglots.txt").read_text(encoding="utf-8").splitlines()
    if line and not line.startswith("#")
]


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Markdown",
        identifier="MD",
        workspace=workspace,
        created_by=create_user,
        intake_view=True,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    return project


@pytest.fixture
def state(db, workspace, project):
    return State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)


@pytest.fixture
def intake(db, workspace, project):
    """The intake endpoint reads this row and dereferences it without a guard,
    so a project with intake_view set but no row answers 500 -- upstream
    behaviour, not something these tests assert on."""

    return Intake.objects.create(name="Intake", project=project, workspace=workspace, is_default=True)


@pytest.fixture
def issue(db, workspace, project, state, create_user):
    return Issue.objects.create(
        name="Existing", workspace=workspace, project=project, state=state, created_by=create_user
    )


def work_items_url(workspace, project):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/"


def executable_markup(rendered_html: str) -> list[str]:
    """What in this document could run, as the browser would see it.

    A substring check would fail the wrong way round: escaped text such as
    `&lt;img onerror=...&gt;` contains the word "onerror" while being inert, and
    that is exactly what correct output looks like. So parse it and ask which
    elements and attributes actually exist.
    """

    document = lxml_html.fragment_fromstring(rendered_html, create_parent="div")
    findings = []
    for element in document.iter():
        tag = str(element.tag).lower()
        if tag in {"script", "iframe", "style", "object", "embed", "svg", "form"}:
            findings.append(f"<{tag}>")
        for name, value in element.attrib.items():
            name = name.lower()
            if name.startswith("on"):
                findings.append(f"{tag}[{name}]")
            if name in {"href", "src", "xlink:href", "action", "formaction"}:
                scheme = str(value).strip().lower().replace("\n", "").replace("\t", "")
                if scheme.startswith("javascript:") or scheme.startswith("data:text/html"):
                    findings.append(f"{tag}[{name}={scheme[:32]}]")
    return findings


def comments_url(workspace, project, issue):
    return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/comments/"


@pytest.mark.contract
class TestWorkItemDescriptionMarkdown:
    @pytest.mark.django_db
    def test_renders_the_common_constructs(self, api_key_client, workspace, project, state):
        markdown = (
            "# Heading\n\n"
            "Some **bold** and `inline` text.\n\n"
            "- first\n- second\n\n"
            "1. one\n2. two\n\n"
            "> quoted\n\n"
            "```\nfenced code\n```\n\n"
            "| a | b |\n| - | - |\n| 1 | 2 |\n\n"
            "~~struck~~\n\n"
            "[link](https://example.com)\n"
        )

        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "From markdown", "state": str(state.id), "description_markdown": markdown},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        html = Issue.objects.get(pk=response.data["id"]).description_html
        for expected in (
            "<h1>Heading</h1>",
            "<strong>bold</strong>",
            "<code>inline</code>",
            "<ul>",
            "<ol>",
            "<blockquote>",
            "<pre>",
            "<table>",
            "<del>struck</del>",
            '<a href="https://example.com"',
        ):
            assert expected in html, f"{expected} missing from {html}"

    @pytest.mark.django_db
    def test_description_markdown_is_write_only(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Write only", "state": str(state.id), "description_markdown": "# Heading"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert "description_markdown" not in response.data
        assert "<h1>Heading</h1>" in response.data["description_html"]

    @pytest.mark.django_db
    def test_populates_the_stripped_description_for_search(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Stripped", "state": str(state.id), "description_markdown": "# Heading\n\nbody text\n"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        stripped = Issue.objects.get(pk=response.data["id"]).description_stripped
        assert "Heading" in stripped and "body text" in stripped
        assert "<h1>" not in stripped

    @pytest.mark.django_db
    def test_update_replaces_the_description(self, api_key_client, workspace, project, issue):
        response = api_key_client.patch(
            f"{work_items_url(workspace, project)}{issue.id}/",
            {"description_markdown": "## Replaced"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        issue.refresh_from_db()
        assert "<h2>Replaced</h2>" in issue.description_html

    @pytest.mark.django_db
    def test_blank_markdown_is_an_empty_document(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Blank", "state": str(state.id), "description_markdown": "   "},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert Issue.objects.get(pk=response.data["id"]).description_html == "<p></p>"


@pytest.mark.contract
class TestMarkdownCannotCarryScript:
    """Every one of these is a stored-XSS attempt through the new input."""

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "markdown",
        [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<iframe src='https://evil.test'></iframe>",
            "[click](javascript:alert(1))",
            "[click](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
            "<a href='javascript:alert(1)'>click</a>",
            "<svg/onload=alert(1)>",
            '<div onmouseover="alert(1)">hover</div>',
            "![x](javascript:alert(1))",
            "<style>body{background:url('javascript:alert(1)')}</style>",
        ],
    )
    def test_no_executable_markup_survives(self, api_key_client, workspace, project, state, markdown):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Hostile", "state": str(state.id), "description_markdown": markdown},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = Issue.objects.get(pk=response.data["id"]).description_html
        assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    def test_html_inside_a_fenced_block_stays_text(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {
                "name": "Fenced",
                "state": str(state.id),
                "description_markdown": "```\n<script>alert(1)</script>\n```",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        html = Issue.objects.get(pk=response.data["id"]).description_html
        assert "<pre>" in html
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


@pytest.mark.contract
class TestPolyglotPayloads:
    """The polyglot corpus, through every surface that takes markdown or HTML.

    A polyglot is one string that tries to break out of attribute, comment,
    tag-name and URL contexts at once, which covers escapes a handwritten
    `<script>alert(1)</script>` never reaches.
    """

    @pytest.mark.django_db
    @pytest.mark.parametrize("payload", POLYGLOTS, ids=range(len(POLYGLOTS)))
    def test_work_item_description_markdown(self, api_key_client, workspace, project, state, payload):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Polyglot", "state": str(state.id), "description_markdown": payload},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = Issue.objects.get(pk=response.data["id"]).description_html
        assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    @pytest.mark.parametrize("payload", POLYGLOTS, ids=range(len(POLYGLOTS)))
    def test_work_item_description_html(self, api_key_client, workspace, project, state, payload):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Polyglot html", "state": str(state.id), "description_html": f"<p>{payload}</p>"},
            format="json",
        )

        # The HTML branch may refuse a payload outright; what it must never do
        # is store something that runs.
        assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST), response.data
        if response.status_code == status.HTTP_201_CREATED:
            rendered = Issue.objects.get(pk=response.data["id"]).description_html
            assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    @pytest.mark.parametrize("payload", POLYGLOTS, ids=range(len(POLYGLOTS)))
    def test_comment_markdown(self, api_key_client, workspace, project, issue, payload):
        response = api_key_client.post(
            comments_url(workspace, project, issue), {"comment_markdown": payload}, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = IssueComment.objects.get(pk=response.data["id"]).comment_html
        assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    @pytest.mark.parametrize("payload", POLYGLOTS, ids=range(len(POLYGLOTS)))
    def test_comment_html(self, api_key_client, workspace, project, issue, payload):
        response = api_key_client.post(
            comments_url(workspace, project, issue), {"comment_html": f"<p>{payload}</p>"}, format="json"
        )

        assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST), response.data
        if response.status_code == status.HTTP_201_CREATED:
            rendered = IssueComment.objects.get(pk=response.data["id"]).comment_html
            assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    @pytest.mark.parametrize("payload", POLYGLOTS, ids=range(len(POLYGLOTS)))
    def test_intake_description_markdown(self, api_key_client, workspace, project, state, intake, payload):
        response = api_key_client.post(
            f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/intake-issues/",
            {"issue": {"name": "Polyglot intake", "description_markdown": payload}},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = Issue.objects.filter(name="Polyglot intake").latest("created_at").description_html
        assert executable_markup(rendered) == [], rendered


@pytest.mark.contract
class TestMarkdownInputBoundaries:
    @pytest.mark.django_db
    def test_both_fields_at_once_is_rejected(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {
                "name": "Ambiguous",
                "state": str(state.id),
                "description_html": "<p>html</p>",
                "description_markdown": "# markdown",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Issue.objects.filter(name="Ambiguous").exists()

    @pytest.mark.django_db
    def test_oversized_markdown_is_rejected(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Huge", "state": str(state.id), "description_markdown": "x" * (MAX_MARKDOWN_SIZE + 1)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Issue.objects.filter(name="Huge").exists()

    @pytest.mark.django_db
    def test_html_input_still_works(self, api_key_client, workspace, project, state):
        response = api_key_client.post(
            work_items_url(workspace, project),
            {"name": "Html", "state": str(state.id), "description_html": "<p>plain <b>html</b></p>"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert "<b>html</b>" in Issue.objects.get(pk=response.data["id"]).description_html


@pytest.mark.contract
class TestCommentMarkdown:
    @pytest.mark.django_db
    def test_html_posted_to_create_is_sanitized(self, api_key_client, workspace, project, issue):
        """Regression: the create serializer had no validation at all, so a
        comment posted as HTML kept its script tags."""

        response = api_key_client.post(
            comments_url(workspace, project, issue),
            {"comment_html": "<p>hi</p><script>alert(1)</script><img src=x onerror=alert(1)>"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = IssueComment.objects.get(pk=response.data["id"]).comment_html
        assert executable_markup(rendered) == [], rendered
        assert "<p>hi</p>" in rendered

    @pytest.mark.django_db
    def test_renders_markdown(self, api_key_client, workspace, project, issue):
        response = api_key_client.post(
            comments_url(workspace, project, issue),
            {"comment_markdown": "**bold** comment\n\n- point\n"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        comment = IssueComment.objects.get(pk=response.data["id"])
        assert "<strong>bold</strong>" in comment.comment_html
        assert "<ul>" in comment.comment_html

    @pytest.mark.django_db
    def test_no_executable_markup_survives(self, api_key_client, workspace, project, issue):
        response = api_key_client.post(
            comments_url(workspace, project, issue),
            {"comment_markdown": "<script>alert(1)</script>[x](javascript:alert(1))"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = IssueComment.objects.get(pk=response.data["id"]).comment_html
        assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    def test_both_fields_at_once_is_rejected(self, api_key_client, workspace, project, issue):
        response = api_key_client.post(
            comments_url(workspace, project, issue),
            {"comment_html": "<p>html</p>", "comment_markdown": "# markdown"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.contract
class TestIntakeMarkdown:
    def intake_url(self, workspace, project):
        return f"/api/v1/workspaces/{workspace.slug}/projects/{project.id}/intake-issues/"

    @pytest.mark.django_db
    def test_renders_markdown(self, api_key_client, workspace, project, state, intake):
        response = api_key_client.post(
            self.intake_url(workspace, project),
            {"issue": {"name": "Filed by a script", "description_markdown": "# Heading\n\n- point\n"}},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        issue = Issue.objects.get(name="Filed by a script")
        assert "<h1>Heading</h1>" in issue.description_html
        assert "<ul>" in issue.description_html

    @pytest.mark.django_db
    def test_no_executable_markup_survives(self, api_key_client, workspace, project, state, intake):
        response = api_key_client.post(
            self.intake_url(workspace, project),
            {"issue": {"name": "Hostile intake", "description_markdown": "<script>alert(1)</script>"}},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        rendered = Issue.objects.get(name="Hostile intake").description_html
        assert executable_markup(rendered) == [], rendered

    @pytest.mark.django_db
    def test_both_fields_at_once_is_rejected(self, api_key_client, workspace, project, state, intake):
        response = api_key_client.post(
            self.intake_url(workspace, project),
            {"issue": {"name": "Ambiguous intake", "description_html": "<p>x</p>", "description_markdown": "# x"}},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not Issue.objects.filter(name="Ambiguous intake").exists()
