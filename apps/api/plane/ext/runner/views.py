# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from functools import wraps

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.db.models import Workspace

from .serializers import RunnerActivationSerializer, RunnerInstallationSerializer, installation_snapshot
from .services import (
    RunnerConsentError,
    RunnerDisabledError,
    RunnerInstallationService,
    RunnerPermissionError,
    RunnerServiceError,
    RunnerTransitionError,
    require_runner_enabled,
)


def runner_error_response(error: RunnerServiceError) -> Response:
    if isinstance(error, RunnerDisabledError):
        response_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, RunnerPermissionError):
        response_status = status.HTTP_403_FORBIDDEN
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


def runner_enabled_endpoint(view_method):
    """Apply the outer gate before request payload validation.

    Services repeat this check intentionally so non-HTTP callers cannot bypass
    the process-level gate.
    """

    @wraps(view_method)
    def wrapped(instance, request, *args, **kwargs):
        try:
            require_runner_enabled()
        except RunnerServiceError as error:
            return runner_error_response(error)
        return view_method(instance, request, *args, **kwargs)

    return wrapped


def installation_response(installation, *, response_status=status.HTTP_200_OK) -> Response:
    snapshot = installation_snapshot(installation)
    return Response(RunnerInstallationSerializer(snapshot).data, status=response_status)


class RunnerInstallationEndpoint(BaseAPIView):
    @runner_enabled_endpoint
    def get(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            installation = RunnerInstallationService.get_for_admin(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return installation_response(installation)

    @runner_enabled_endpoint
    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            RunnerInstallationService.authorize_admin(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)

        serializer = RunnerActivationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = RunnerInstallationService.activate(
                workspace=workspace,
                actor=request.user,
                consent_version=serializer.validated_data["consent_version"],
                consent_digest=serializer.validated_data["consent_digest"],
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return installation_response(result.installation, response_status=response_status)


class RunnerInstallationSuspendEndpoint(BaseAPIView):
    @runner_enabled_endpoint
    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            result = RunnerInstallationService.suspend(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return installation_response(result.installation)


class RunnerInstallationRevokeEndpoint(BaseAPIView):
    @runner_enabled_endpoint
    def post(self, request, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        try:
            result = RunnerInstallationService.revoke(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return installation_response(result.installation)
