# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What a published project board (Spaces) says about people.

A published board is readable by anyone who has its link, without signing in.
It shows the work items, and the comments, votes and reactions left on them.
It does not show who the project's members are or who a work item is assigned
to, so its API must not either:

- no ``assignee_ids`` or ``created_by`` on work items, no member roster, and
  no grouping, filtering or ordering keyed on a member;
- someone who commented, voted or reacted on the board appears with the public
  actor shape only: ``id``, ``display_name``, ``avatar_url``, ``is_bot`` —
  never an email, a first or last name, or the raw avatar field;
- the board settings do not name who published or last changed the board;
- the intake list a signed-in visitor can read carries no assignees.

FORK.md, security invariant S30.
"""

from unittest import mock
from uuid import uuid4

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    CommentReaction,
    Cycle,
    DeployBoard,
    Intake,
    IntakeIssue,
    Issue,
    IssueAssignee,
    IssueComment,
    IssueReaction,
    IssueVote,
    Label,
    Module,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)

PUBLIC_ACTOR_FIELDS = {"id", "display_name", "avatar_url", "is_bot"}


def _person(label, workspace=None):
    """A user whose every identifying string is unique and greppable."""
    uid = uuid4().hex[:8]
    user = User.objects.create(
        email=f"{label}-{uid}@people.example",
        username=f"{label}_{uid}",
        first_name=f"First{label.capitalize()}{uid}",
        last_name=f"Last{label.capitalize()}{uid}",
        display_name=f"{label}-display-{uid}",
        avatar=f"https://avatars.example/{label}-{uid}.png",
    )
    if workspace is not None:
        WorkspaceMember.objects.create(workspace=workspace, member=user, role=15)
    return user


def _stamp(obj, created_by, updated_by=None):
    """BaseModel.save() takes the audit users from the request, so set them after."""
    type(obj).objects.filter(pk=obj.pk).update(created_by=created_by, updated_by=updated_by)
    obj.refresh_from_db()
    return obj


def _secrets(user):
    """What the board never says about anyone, actors included."""
    return [user.email, user.first_name, user.last_name]


def _names(user):
    """Everything that identifies someone who did not act on the board."""
    return [*_secrets(user), user.display_name, user.avatar]


def _all_strings(user):
    return [*_names(user), str(user.id)]


@pytest.fixture(autouse=True)
def _clean_throttle_and_activity(db):
    """Anonymous requests share one throttle bucket; start every test empty."""
    cache.clear()
    with (
        mock.patch("plane.space.views.issue.issue_activity"),
        mock.patch("plane.space.views.intake.issue_activity"),
    ):
        yield
    cache.clear()


@pytest.fixture
def people(db, workspace):
    return {
        # project members who never acted on the board
        "assignee": _person("assignee", workspace),
        "creator": _person("creator", workspace),
        "mentioned": _person("mentioned", workspace),
        "bystander": _person("bystander", workspace),
        "publisher": _person("publisher", workspace),
        # people who acted on the board
        "commenter": _person("commenter"),
        "voter": _person("voter"),
        "reactor": _person("reactor"),
        "comment_reactor": _person("creactor"),
        # a signed-in visitor with no role in the project
        "visitor": _person("visitor"),
    }


@pytest.fixture
def board(db, workspace, people):
    project = Project.objects.create(name="Public Board", identifier="PUB", workspace=workspace)
    for key in ("assignee", "creator", "mentioned", "bystander", "publisher"):
        ProjectMember.objects.create(project=project, member=people[key], workspace=workspace, role=15, is_active=True)
    state = State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)
    triage = State.objects.create(name="Triage", project=project, workspace=workspace, group="triage")
    Label.objects.create(name="Bug", project=project, workspace=workspace)
    Cycle.objects.create(name="Sprint", project=project, workspace=workspace, owned_by=people["publisher"])
    Module.objects.create(name="Module", project=project, workspace=workspace)
    mention = (
        f'<p>Ping <mention-component entity_identifier="{people["mentioned"].id}" '
        'entity_name="user_mention"></mention-component></p>'
    )
    issue = Issue.objects.create(
        name="Public work item",
        description_html=mention,
        workspace=workspace,
        project=project,
        state=state,
    )
    _stamp(issue, people["creator"])
    IssueAssignee.objects.create(issue=issue, assignee=people["assignee"], project=project)
    comment = IssueComment.objects.create(
        issue=issue,
        project=project,
        comment_html="<p>a public comment</p>",
        access="EXTERNAL",
        actor=people["commenter"],
    )
    _stamp(comment, people["commenter"], people["bystander"])
    IssueVote.objects.create(issue=issue, actor=people["voter"], project=project, vote=1)
    IssueReaction.objects.create(issue=issue, actor=people["reactor"], project=project, reaction="1f44d")
    comment_reaction = CommentReaction.objects.create(
        comment=comment, actor=people["comment_reactor"], project=project, reaction="1f389"
    )
    _stamp(comment_reaction, people["comment_reactor"], people["bystander"])
    intake = Intake.objects.create(name="Intake", project=project, workspace=workspace)
    intake_item = Issue.objects.create(
        name="Intake work item",
        workspace=workspace,
        project=project,
        state=triage,
    )
    _stamp(intake_item, people["creator"])
    IssueAssignee.objects.create(issue=intake_item, assignee=people["assignee"], project=project)
    intake_issue = IntakeIssue.objects.create(intake=intake, issue=intake_item, project=project)
    deploy_board = DeployBoard.objects.create(
        entity_name="project",
        entity_identifier=project.id,
        project=project,
        workspace=workspace,
        is_comments_enabled=True,
        is_reactions_enabled=True,
        is_votes_enabled=True,
        intake=intake,
    )
    _stamp(deploy_board, people["publisher"], people["publisher"])
    return {
        "project": project,
        "issue": issue,
        "comment": comment,
        "intake": intake,
        "intake_issue": intake_issue,
        "anchor": deploy_board.anchor,
        "workspace": workspace,
    }


def _issues(board, **params):
    return APIClient().get(f"/api/public/anchor/{board['anchor']}/issues/", params)


def _issue_rows(payload):
    """Every work item in a paginated public issue list, grouped or not."""
    results = payload["results"]
    if isinstance(results, list):
        return results
    rows = []
    for group in results.values():
        inner = group["results"]
        if isinstance(inner, list):
            rows.extend(inner)
        else:
            for sub in inner.values():
                rows.extend(sub["results"])
    return rows


def _assert_public_actor(actor):
    assert set(actor) == PUBLIC_ACTOR_FIELDS, actor


def _assert_absent(body, *users):
    for user in users:
        for value in _all_strings(user):
            assert value not in body, f"{value!r} leaked"


def _assert_unnamed(body, *users):
    for user in users:
        for value in _names(user):
            assert value not in body, f"{value!r} leaked"


def _assert_no_secrets(body, *users):
    for user in users:
        for value in _secrets(user):
            assert value not in body, f"{value!r} leaked"


@pytest.mark.contract
@pytest.mark.django_db
class TestPublicIssueList:
    @pytest.mark.parametrize(
        "params", [{}, {"group_by": "state_id"}, {"group_by": "priority", "sub_group_by": "state_id"}]
    )
    def test_work_items_carry_no_assignees_or_creator(self, board, people, params):
        response = _issues(board, **params)

        assert response.status_code == status.HTTP_200_OK
        rows = _issue_rows(response.json())
        assert rows
        for row in rows:
            assert "assignee_ids" not in row
            assert "created_by" not in row
        _assert_absent(response.content.decode(), people["assignee"], people["creator"], people["bystander"])

    def test_votes_and_reactions_carry_the_public_actor_only(self, board, people):
        response = _issues(board)

        row = _issue_rows(response.json())[0]
        assert [v["actor_details"]["display_name"] for v in row["vote_items"]] == [people["voter"].display_name]
        assert [r["actor_details"]["display_name"] for r in row["reaction_items"]] == [people["reactor"].display_name]
        for item in row["vote_items"] + row["reaction_items"]:
            _assert_public_actor(item["actor_details"])
        _assert_no_secrets(response.content.decode(), people["voter"], people["reactor"])

    @pytest.mark.parametrize("field", ["group_by", "sub_group_by"])
    @pytest.mark.parametrize("value", ["assignees__id", "created_by"])
    def test_grouping_by_a_person_is_refused(self, board, people, field, value):
        params = {field: value}
        if field == "sub_group_by":
            params["group_by"] = "state_id"

        response = _issues(board, **params)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        _assert_absent(response.content.decode(), people["assignee"], people["creator"], people["bystander"])

    @pytest.mark.parametrize("key", ["assignees", "created_by", "mentions", "subscriber", "logged_by"])
    def test_filtering_by_a_person_is_ignored(self, board, key):
        """Otherwise the board answers "is this user assigned/mentioned here?"."""
        response = _issues(board, **{key: str(uuid4())})

        assert response.status_code == status.HTTP_200_OK
        assert [row["id"] for row in _issue_rows(response.json())] == [str(board["issue"].id)]

    def test_ordering_by_assignee_name_falls_back(self, board):
        response = _issues(board, order_by="assignees__first_name")

        assert response.status_code == status.HTTP_200_OK
        assert [row["id"] for row in _issue_rows(response.json())] == [str(board["issue"].id)]


@pytest.mark.contract
@pytest.mark.django_db
class TestPublicIssueDetail:
    def test_detail_carries_no_assignees_or_creator(self, board, people):
        response = APIClient().get(f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/")

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["id"] == str(board["issue"].id)
        assert "assignee_ids" not in payload
        assert "created_by" not in payload
        assert [v["actor_details"]["display_name"] for v in payload["vote_items"]] == [people["voter"].display_name]
        assert [r["actor_details"]["display_name"] for r in payload["reaction_items"]] == [
            people["reactor"].display_name
        ]
        for item in payload["vote_items"] + payload["reaction_items"]:
            _assert_public_actor(item["actor_details"])
        body = response.content.decode()
        _assert_absent(body, people["assignee"], people["creator"], people["bystander"])
        _assert_no_secrets(body, people["voter"], people["reactor"])
        # The mention's user id stays in the stored rich text; nothing resolves it to a name.
        _assert_unnamed(body, people["mentioned"])

    def test_reaction_avatar_is_the_reactors_own(self, board, people):
        response = APIClient().get(f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/")

        (reaction,) = response.json()["reaction_items"]
        assert reaction["actor_details"]["avatar_url"] == people["reactor"].avatar


@pytest.mark.contract
@pytest.mark.django_db
class TestMemberRoster:
    def test_the_member_roster_is_not_served(self, board, people):
        response = APIClient().get(f"/api/public/anchor/{board['anchor']}/members/")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        _assert_absent(response.content.decode(), people["assignee"], people["bystander"])


@pytest.mark.contract
@pytest.mark.django_db
class TestPublicComments:
    def test_comment_author_and_reactors_carry_the_public_shape_only(self, board, people):
        response = APIClient().get(f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/comments/")

        assert response.status_code == status.HTTP_200_OK
        (comment,) = response.json()
        _assert_public_actor(comment["actor_detail"])
        assert comment["actor_detail"]["display_name"] == people["commenter"].display_name
        assert comment["actor_detail"]["avatar_url"] == people["commenter"].avatar
        assert "created_by" not in comment and "updated_by" not in comment
        (reaction,) = comment["comment_reactions"]
        assert reaction["display_name"] == people["comment_reactor"].display_name
        assert "created_by" not in reaction and "updated_by" not in reaction
        body = response.content.decode()
        _assert_no_secrets(body, people["commenter"], people["comment_reactor"])
        _assert_absent(body, people["bystander"])

    def test_comment_reactions_list_has_no_audit_users(self, board, people):
        client = APIClient()
        client.force_authenticate(user=people["visitor"])

        response = client.get(f"/api/public/anchor/{board['anchor']}/comments/{board['comment'].id}/reactions/")

        assert response.status_code == status.HTTP_200_OK
        (reaction,) = response.json()
        assert "created_by" not in reaction and "updated_by" not in reaction
        _assert_absent(response.content.decode(), people["bystander"])

    def test_a_new_comment_answers_with_the_public_shape(self, board, people):
        client = APIClient()
        client.force_authenticate(user=people["visitor"])

        response = client.post(
            f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/comments/",
            {"comment_html": "<p>hello</p>"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        _assert_public_actor(response.json()["actor_detail"])
        assert "created_by" not in response.json()

    def test_a_vote_answers_with_the_public_shape(self, board, people):
        client = APIClient()
        client.force_authenticate(user=people["visitor"])

        response = client.post(
            f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/votes/", {"vote": 1}, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        _assert_public_actor(response.json()["actor_detail"])

    def test_a_reaction_answers_with_the_public_shape(self, board, people):
        client = APIClient()
        client.force_authenticate(user=people["visitor"])

        response = client.post(
            f"/api/public/anchor/{board['anchor']}/issues/{board['issue'].id}/reactions/",
            {"reaction": "1f680"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        _assert_public_actor(response.json()["actor_detail"])


@pytest.mark.contract
@pytest.mark.django_db
class TestBoardSettings:
    def test_settings_do_not_name_the_publisher(self, board, people):
        response = APIClient().get(f"/api/public/anchor/{board['anchor']}/settings/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["anchor"] == board["anchor"]
        assert "created_by" not in response.json() and "updated_by" not in response.json()
        _assert_absent(response.content.decode(), people["publisher"])

    def test_anchor_lookup_does_not_name_the_publisher(self, board, people):
        workspace = board["workspace"]
        response = APIClient().get(f"/api/public/workspaces/{workspace.slug}/projects/{board['project'].id}/anchor/")

        assert response.status_code == status.HTTP_200_OK
        assert "created_by" not in response.json() and "updated_by" not in response.json()
        _assert_absent(response.content.decode(), people["publisher"])


@pytest.mark.contract
@pytest.mark.django_db
class TestPublicIntake:
    def _client(self, people):
        client = APIClient()
        client.force_authenticate(user=people["visitor"])
        return client

    def test_intake_list_carries_no_assignees(self, board, people):
        response = self._client(people).get(
            f"/api/public/anchor/{board['anchor']}/intakes/{board['intake'].id}/intake-issues/"
        )

        assert response.status_code == status.HTTP_200_OK
        (row,) = response.json()
        for key in ("assignees", "assignee_details", "created_by", "updated_by"):
            assert key not in row
        _assert_absent(response.content.decode(), people["assignee"], people["creator"])

    def test_intake_detail_carries_no_assignees(self, board, people):
        response = self._client(people).get(
            f"/api/public/anchor/{board['anchor']}/intakes/{board['intake'].id}/intake-issues/{board['intake_issue'].id}/"
        )

        assert response.status_code == status.HTTP_200_OK
        for key in ("assignees", "assignee_details", "created_by", "updated_by"):
            assert key not in response.json()
        _assert_absent(response.content.decode(), people["assignee"], people["creator"])

    def test_intake_list_ignores_person_filters(self, board, people):
        response = self._client(people).get(
            f"/api/public/anchor/{board['anchor']}/intakes/{board['intake'].id}/intake-issues/",
            {"assignees": str(uuid4())},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 1


@pytest.mark.contract
@pytest.mark.django_db
def test_an_anonymous_reader_learns_only_who_acted_on_the_board(board, people):
    """Read every public GET a visitor's browser makes; only actors are named."""
    anchor, issue_id = board["anchor"], board["issue"].id
    client = APIClient()
    paths = [
        "meta/",
        "settings/",
        "issues/",
        "issues/?group_by=state_id",
        f"issues/{issue_id}/",
        f"issues/{issue_id}/comments/",
        "states/",
        "labels/",
        "cycles/",
        "modules/",
        "members/",
    ]
    body = "".join(client.get(f"/api/public/anchor/{anchor}/{path}").content.decode() for path in paths)

    for key in ("assignee", "creator", "bystander", "publisher"):
        _assert_absent(body, people[key])
    # The mention's user id stays in the stored rich text; nothing resolves it to a name.
    _assert_unnamed(body, people["mentioned"])
    for key in ("commenter", "voter", "reactor", "comment_reactor"):
        assert people[key].display_name in body
        _assert_no_secrets(body, people[key])
