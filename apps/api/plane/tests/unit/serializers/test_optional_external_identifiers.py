# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from uuid import uuid4

import pytest

from plane.api.serializers.issue import (
    IssueCommentCreateSerializer as APIIssueCommentCreateSerializer,
)
from plane.api.serializers.issue import IssueSerializer as APIIssueSerializer
from plane.app.serializers import IssueCommentSerializer as AppIssueCommentSerializer
from plane.app.serializers import IssueCreateSerializer as AppIssueCreateSerializer
from plane.space.serializer.issue import IssueCommentSerializer as SpaceIssueCommentSerializer
from plane.space.serializer.issue import IssueCreateSerializer as SpaceIssueCreateSerializer


@pytest.mark.parametrize(
    "serializer_class",
    [AppIssueCreateSerializer, APIIssueSerializer, SpaceIssueCreateSerializer],
)
def test_work_item_external_identifiers_are_optional(serializer_class):
    serializer = serializer_class(
        data={"name": "Normal work item"},
        context={
            "project_id": uuid4(),
            "workspace_id": uuid4(),
            "default_assignee_id": None,
        },
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data.get("external_source") is None
    assert serializer.validated_data.get("external_id") is None


@pytest.mark.parametrize(
    "serializer_class",
    [AppIssueCommentSerializer, APIIssueCommentCreateSerializer, SpaceIssueCommentSerializer],
)
def test_comment_external_identifiers_are_optional(serializer_class):
    serializer = serializer_class(data={"comment_html": "<p>Normal comment</p>"})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data.get("external_source") is None
    assert serializer.validated_data.get("external_id") is None
