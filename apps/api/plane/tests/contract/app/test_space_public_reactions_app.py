# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Reactions and votes on a published project board (Spaces).

- A work item nobody has reacted to or voted on answers ``reaction_items: []``
  and ``vote_items: []``, never ``null``. Spaces spread ``reaction_items`` into
  a new array before posting the first reaction; ``null`` made that throw, so
  the first reaction on a work item was never sent.
- ``anchor/<anchor>/issues/<id>/votes/`` and ``…/reactions/`` list what is
  stored. Both looked the board up by URL arguments their routes do not supply
  (the anchor as a workspace slug, a ``slug`` and ``project_id`` that are never
  there), so they always answered ``[]``. Spaces reloads from them when a write
  fails.
- Both lists keep the public actor shape (FORK.md S30) and show only work items
  the board shows.
"""

from unittest import mock
from uuid import uuid4

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import (
    DeployBoard,
    Intake,
    IntakeIssue,
    Issue,
    IssueReaction,
    IssueVote,
    Project,
    State,
    User,
)

PUBLIC_ACTOR_FIELDS = {"id", "display_name", "avatar_url", "is_bot"}


def _person(label):
    uid = uuid4().hex[:8]
    return User.objects.create(
        email=f"{label}-{uid}@people.example",
        username=f"{label}_{uid}",
        first_name=f"First{uid}",
        last_name=f"Last{uid}",
        display_name=f"{label}-display-{uid}",
    )


@pytest.fixture(autouse=True)
def _quiet(db):
    cache.clear()
    with mock.patch("plane.space.views.issue.issue_activity"):
        yield
    cache.clear()


@pytest.fixture
def board(db, workspace):
    project = Project.objects.create(name="Reactions Board", identifier=f"R{uuid4().hex[:4]}", workspace=workspace)
    state = State.objects.create(name="Todo", project=project, workspace=workspace, group="backlog", default=True)
    triage = State.objects.create(name="Triage", project=project, workspace=workspace, group="triage")
    voter, reactor, visitor = _person("voter"), _person("reactor"), _person("visitor")
    acted_on = Issue.objects.create(name="Acted on", workspace=workspace, project=project, state=state)
    untouched = Issue.objects.create(name="Untouched", workspace=workspace, project=project, state=state)
    IssueVote.objects.create(issue=acted_on, actor=voter, project=project, vote=1)
    IssueReaction.objects.create(issue=acted_on, actor=reactor, project=project, reaction="1f44d")
    intake = Intake.objects.create(name="Intake", project=project, workspace=workspace)
    triaged = Issue.objects.create(name="In triage", workspace=workspace, project=project, state=triage)
    IntakeIssue.objects.create(intake=intake, issue=triaged, project=project)
    IssueVote.objects.create(issue=triaged, actor=voter, project=project, vote=1)
    IssueReaction.objects.create(issue=triaged, actor=reactor, project=project, reaction="1f44d")
    deploy_board = DeployBoard.objects.create(
        entity_name="project",
        entity_identifier=project.id,
        project=project,
        workspace=workspace,
        is_reactions_enabled=True,
        is_votes_enabled=True,
    )
    client = APIClient()
    client.force_authenticate(user=visitor)
    return {
        "anchor": deploy_board.anchor,
        "deploy_board": deploy_board,
        "acted_on": acted_on,
        "untouched": untouched,
        "triaged": triaged,
        "voter": voter,
        "reactor": reactor,
        "visitor": visitor,
        "client": client,
    }


def _url(board, issue, suffix=""):
    return f"/api/public/anchor/{board['anchor']}/issues/{issue.id}/{suffix}"


def _rows(payload):
    results = payload["results"]
    if isinstance(results, list):
        return results
    return [row for group in results.values() for row in group["results"]]


@pytest.mark.contract
@pytest.mark.django_db
class TestEmptyReactionAndVoteItems:
    def test_detail_answers_empty_lists(self, board):
        response = APIClient().get(_url(board, board["untouched"]))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["reaction_items"] == []
        assert response.json()["vote_items"] == []

    @pytest.mark.parametrize("params", [{}, {"group_by": "state_id"}])
    def test_list_answers_empty_lists(self, board, params):
        response = APIClient().get(f"/api/public/anchor/{board['anchor']}/issues/", params)

        assert response.status_code == status.HTTP_200_OK
        (row,) = [row for row in _rows(response.json()) if row["id"] == str(board["untouched"].id)]
        assert row["reaction_items"] == []
        assert row["vote_items"] == []

    def test_the_first_reaction_is_stored_and_shown(self, board):
        client = board["client"]

        before = client.get(_url(board, board["untouched"])).json()["reaction_items"]
        created = client.post(_url(board, board["untouched"], "reactions/"), {"reaction": "1f680"}, format="json")
        detail = client.get(_url(board, board["untouched"])).json()
        listed = client.get(_url(board, board["untouched"], "reactions/")).json()

        assert before == []
        assert created.status_code == status.HTTP_201_CREATED
        assert set(created.json()["actor_detail"]) == PUBLIC_ACTOR_FIELDS
        assert [(r["reaction"], r["actor_details"]["id"]) for r in detail["reaction_items"]] == [
            ("1f680", str(board["visitor"].id))
        ]
        assert set(detail["reaction_items"][0]["actor_details"]) == PUBLIC_ACTOR_FIELDS
        assert detail["vote_items"] == []
        assert [(r["reaction"], r["actor_detail"]["id"]) for r in listed] == [("1f680", str(board["visitor"].id))]

    def test_the_first_vote_is_stored_and_shown(self, board):
        client = board["client"]

        created = client.post(_url(board, board["untouched"], "votes/"), {"vote": -1}, format="json")
        detail = client.get(_url(board, board["untouched"])).json()

        assert created.status_code == status.HTTP_201_CREATED
        assert [(v["vote"], v["actor_details"]["id"]) for v in detail["vote_items"]] == [(-1, str(board["visitor"].id))]
        assert detail["reaction_items"] == []


@pytest.mark.contract
@pytest.mark.django_db
class TestReactionAndVoteLists:
    def test_votes_list_returns_the_stored_vote(self, board):
        response = board["client"].get(_url(board, board["acted_on"], "votes/"))

        assert response.status_code == status.HTTP_200_OK
        (vote,) = response.json()
        assert vote["vote"] == 1
        assert set(vote["actor_detail"]) == PUBLIC_ACTOR_FIELDS
        assert vote["actor_detail"]["id"] == str(board["voter"].id)
        assert vote["actor_detail"]["display_name"] == board["voter"].display_name
        assert board["voter"].email not in response.content.decode()

    def test_reactions_list_returns_the_stored_reaction(self, board):
        response = board["client"].get(_url(board, board["acted_on"], "reactions/"))

        assert response.status_code == status.HTTP_200_OK
        (reaction,) = response.json()
        assert reaction["reaction"] == "1f44d"
        assert set(reaction["actor_detail"]) == PUBLIC_ACTOR_FIELDS
        assert reaction["actor_detail"]["id"] == str(board["reactor"].id)
        assert "created_by" not in reaction
        assert board["reactor"].email not in response.content.decode()

    @pytest.mark.parametrize("suffix", ["votes/", "reactions/"])
    def test_a_work_item_the_board_does_not_show_lists_nothing(self, board, suffix):
        response = board["client"].get(_url(board, board["triaged"], suffix))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.parametrize(
        ("suffix", "flag"), [("votes/", "is_votes_enabled"), ("reactions/", "is_reactions_enabled")]
    )
    def test_a_disabled_board_feature_lists_nothing(self, board, suffix, flag):
        DeployBoard.objects.filter(pk=board["deploy_board"].pk).update(**{flag: False})

        response = board["client"].get(_url(board, board["acted_on"], suffix))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    @pytest.mark.parametrize("suffix", ["votes/", "reactions/"])
    def test_a_disabled_board_lists_nothing(self, board, suffix):
        DeployBoard.objects.filter(pk=board["deploy_board"].pk).update(is_disabled=True)

        response = board["client"].get(_url(board, board["acted_on"], suffix))

        assert response.status_code in (status.HTTP_200_OK, status.HTTP_404_NOT_FOUND)
        if response.status_code == status.HTTP_200_OK:
            assert response.json() == []
