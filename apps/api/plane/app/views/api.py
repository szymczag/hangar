# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python import
import os
from uuid import uuid4
from typing import Optional

# Third party
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status

# Module import
from .base import BaseAPIView
from plane.db.models import APIToken, WorkspaceMember
from plane.app.serializers import APITokenSerializer, APITokenReadSerializer
from plane.license.utils.instance_value import get_configuration_value

# Fork (see FORK.md): a token used to be minted by anyone signed in and reached
# every workspace its owner belonged to, so a guest in one workspace could act
# through it in another where they were an administrator. A token now names the
# workspace it is for — BaseAPIView.initial() already confines a token that does
# — and minting one requires holding a role there.
DEFAULT_MINIMUM_ROLE = 5


def _minimum_role() -> int:
    (configured,) = get_configuration_value(
        [
            {
                "key": "API_TOKEN_MINIMUM_ROLE",
                "default": os.environ.get("API_TOKEN_MINIMUM_ROLE", str(DEFAULT_MINIMUM_ROLE)),
            }
        ]
    )
    try:
        return int(configured)
    except (TypeError, ValueError):
        # An unreadable setting must not hand out tokens more freely than the
        # administrator intended, but it also must not lock everyone out of a
        # feature that worked yesterday.
        return DEFAULT_MINIMUM_ROLE


class ApiTokenEndpoint(BaseAPIView):
    def post(self, request: Request) -> Response:
        label = request.data.get("label", str(uuid4().hex))
        description = request.data.get("description", "")
        expired_at = request.data.get("expired_at", None)
        workspace_slug = (request.data.get("workspace_slug") or "").strip()

        if not workspace_slug:
            return Response(
                {"error": "Choose the workspace this token may act in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = WorkspaceMember.objects.filter(
            workspace__slug=workspace_slug,
            member=request.user,
            is_active=True,
        ).first()
        if membership is None:
            # Deliberately the same answer as an unknown slug: whether a
            # workspace exists is not something a non-member should learn here.
            return Response(
                {"error": "You are not a member of that workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )

        minimum_role = _minimum_role()
        if membership.role < minimum_role:
            return Response(
                {"error": "Your role in this workspace does not allow creating API tokens."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check the user type
        user_type = 1 if request.user.is_bot else 0

        api_token = APIToken.objects.create(
            label=label,
            description=description,
            user=request.user,
            user_type=user_type,
            expired_at=expired_at,
            workspace_id=membership.workspace_id,
        )

        serializer = APITokenSerializer(api_token)
        # Token will be only visible while creating
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request: Request, pk: Optional[str] = None) -> Response:
        if pk is None:
            api_tokens = APIToken.objects.filter(user=request.user, is_service=False)
            serializer = APITokenReadSerializer(api_tokens, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            api_tokens = APIToken.objects.get(user=request.user, pk=pk, is_service=False)
            serializer = APITokenReadSerializer(api_tokens)
            return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request: Request, pk: str) -> Response:
        api_token = APIToken.objects.get(user=request.user, pk=pk, is_service=False)
        api_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request: Request, pk: str) -> Response:
        api_token = APIToken.objects.get(user=request.user, pk=pk, is_service=False)
        serializer = APITokenSerializer(api_token, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Answered with the read serializer, which excludes `token`. Writing
            # through APITokenSerializer is right — its read_only_fields protect
            # the secret and the ownership fields from being set — but echoing
            # its output would hand the secret back on every rename. Creation is
            # the one moment the token is legitimately shown.
            return Response(APITokenReadSerializer(api_token).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
