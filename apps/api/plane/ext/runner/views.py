# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import Workspace

from .serializers import (
    RunnerActivationSerializer,
    RunnerInstallationSerializer,
    inactive_installation_payload,
)
from .services import (
    RunnerConsentError,
    RunnerDisabledError,
    RunnerInstallationService,
    RunnerServiceError,
    RunnerTransitionError,
    require_runner_enabled,
)


def runner_error_response(error: RunnerServiceError) -> Response:
    if isinstance(error, RunnerDisabledError):
        response_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, RunnerConsentError):
        response_status = status.HTTP_400_BAD_REQUEST
    elif isinstance(error, RunnerTransitionError):
        response_status = status.HTTP_409_CONFLICT
    else:
        response_status = status.HTTP_400_BAD_REQUEST
    return Response(
        {"error": str(error), "code": error.code},
        status=response_status,
    )


class RunnerInstallationEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def get(self, request, slug):
        try:
            require_runner_enabled()
        except RunnerServiceError as error:
            return runner_error_response(error)

        workspace = get_object_or_404(Workspace, slug=slug)
        installation = RunnerInstallationService.get(workspace)
        if installation is None:
            return Response(inactive_installation_payload(), status=status.HTTP_200_OK)
        return Response(
            RunnerInstallationSerializer(installation).data,
            status=status.HTTP_200_OK,
        )

    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        try:
            require_runner_enabled()
        except RunnerServiceError as error:
            return runner_error_response(error)

        serializer = RunnerActivationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            installation, created = RunnerInstallationService.activate(
                workspace=workspace,
                actor=request.user,
                consent_version=serializer.validated_data["consent_version"],
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return Response(
            RunnerInstallationSerializer(installation).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class RunnerInstallationSuspendEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        try:
            require_runner_enabled()
        except RunnerServiceError as error:
            return runner_error_response(error)

        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            installation, _changed = RunnerInstallationService.suspend(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return Response(
            RunnerInstallationSerializer(installation).data,
            status=status.HTTP_200_OK,
        )


class RunnerInstallationRevokeEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN], level="WORKSPACE")
    def post(self, request, slug):
        try:
            require_runner_enabled()
        except RunnerServiceError as error:
            return runner_error_response(error)

        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            installation, _changed = RunnerInstallationService.revoke(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return Response(
            RunnerInstallationSerializer(installation).data,
            status=status.HTTP_200_OK,
        )
