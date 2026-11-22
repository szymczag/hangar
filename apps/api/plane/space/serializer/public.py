# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""What a published project board says about people.

A published board is readable by anyone who has its link, without signing in.
These serializers are the app serializers the board used to answer with, less
the people the board has no reason to name (FORK.md, S30):

- someone who commented, voted or reacted on the board appears as the public
  actor: ``id`` (so the viewer's browser can tell its own reactions and
  comments apart), ``display_name`` and ``avatar_url`` (what the board shows)
  and ``is_bot`` (the "Bot" label) -- never an email, first or last name or the
  raw ``avatar`` field;
- the audit users (``created_by``, ``updated_by``) are left out everywhere: on a
  comment the editor can be a project admin, on the board it is whoever
  published it, neither of whom acted on the board;
- work items carry no assignees.
"""

from plane.app.serializers import (
    CommentReactionSerializer,
    DeployBoardSerializer,
    IssueCommentSerializer,
    IssueReactionSerializer,
    IssueStateIntakeSerializer,
    IssueVoteSerializer,
)
from plane.db.models import User

from .base import BaseSerializer

PUBLIC_ACTOR_FIELDS = ("id", "display_name", "avatar_url", "is_bot")
AUDIT_USER_FIELDS = ("created_by", "updated_by")


def _without(fields, removed):
    return [field for field in fields if field not in removed]


class PublicActorSerializer(BaseSerializer):
    class Meta:
        model = User
        fields = list(PUBLIC_ACTOR_FIELDS)
        read_only_fields = fields


class PublicCommentReactionSerializer(CommentReactionSerializer):
    class Meta(CommentReactionSerializer.Meta):
        fields = _without(CommentReactionSerializer.Meta.fields, AUDIT_USER_FIELDS)
        read_only_fields = _without(CommentReactionSerializer.Meta.read_only_fields, AUDIT_USER_FIELDS)


class PublicIssueCommentSerializer(IssueCommentSerializer):
    actor_detail = PublicActorSerializer(read_only=True, source="actor")
    comment_reactions = PublicCommentReactionSerializer(read_only=True, many=True)

    class Meta(IssueCommentSerializer.Meta):
        fields = None
        exclude = AUDIT_USER_FIELDS
        read_only_fields = _without(IssueCommentSerializer.Meta.read_only_fields, AUDIT_USER_FIELDS)


class PublicIssueReactionSerializer(IssueReactionSerializer):
    actor_detail = PublicActorSerializer(read_only=True, source="actor")

    class Meta(IssueReactionSerializer.Meta):
        fields = None
        exclude = AUDIT_USER_FIELDS


class PublicIssueVoteSerializer(IssueVoteSerializer):
    actor_detail = PublicActorSerializer(read_only=True, source="actor")


class PublicDeployBoardSerializer(DeployBoardSerializer):
    class Meta(DeployBoardSerializer.Meta):
        fields = None
        exclude = AUDIT_USER_FIELDS


class PublicIntakeIssueSerializer(IssueStateIntakeSerializer):
    # Removes the parent's declared field: an intake item can be assigned once it
    # is triaged, and the board does not say to whom.
    assignee_details = None

    class Meta(IssueStateIntakeSerializer.Meta):
        fields = None
        exclude = ("assignees", *AUDIT_USER_FIELDS)
