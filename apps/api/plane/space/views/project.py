# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db.models import Exists, OuterRef

# Third Party imports
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

# Module imports
from .base import BaseAPIView
from plane.db.models import Project, DeployBoard
from plane.space.serializer.public import PublicDeployBoardSerializer


class ProjectDeployBoardPublicSettingsEndpoint(BaseAPIView):
    permission_classes = [AllowAny]

    def get(self, request, anchor):
        project_deploy_board = DeployBoard.objects.get(
            anchor=anchor,
            entity_name="project",
            is_disabled=False,
        )
        # Fork (see FORK.md, S30): without the audit users who published the board.
        serializer = PublicDeployBoardSerializer(project_deploy_board)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WorkspaceProjectDeployBoardEndpoint(BaseAPIView):
    permission_classes = [AllowAny]

    def get(self, request, anchor):
        deploy_board = DeployBoard.objects.get(
            anchor=anchor,
            entity_name="project",
            is_disabled=False,
        )
        projects = (
            Project.objects.filter(workspace=deploy_board.workspace)
            .annotate(
                is_public=Exists(
                    DeployBoard.objects.filter(
                        anchor=anchor,
                        project_id=OuterRef("pk"),
                        entity_name="project",
                        is_disabled=False,
                    )
                )
            )
            .filter(is_public=True)
        ).values(
            "id",
            "identifier",
            "name",
            "description",
            "emoji",
            "icon_prop",
            "cover_image",
        )

        return Response(projects, status=status.HTTP_200_OK)


class WorkspaceProjectAnchorEndpoint(BaseAPIView):
    permission_classes = [AllowAny]

    def get(self, request, slug, project_id):
        project_deploy_board = DeployBoard.objects.get(
            workspace__slug=slug,
            project_id=project_id,
            entity_identifier=project_id,
            entity_name="project",
            is_disabled=False,
        )
        # Fork (see FORK.md, S30): without the audit users who published the board.
        serializer = PublicDeployBoardSerializer(project_deploy_board)
        return Response(serializer.data, status=status.HTTP_200_OK)
