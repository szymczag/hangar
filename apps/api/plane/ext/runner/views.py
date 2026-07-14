# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from functools import wraps
from ipaddress import ip_address
from uuid import uuid4

from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView

from .serializers import RunnerActivationSerializer, RunnerInstallationSerializer, installation_snapshot
from .services import (
    RunnerAuditContext,
    RunnerConsentError,
    RunnerDisabledError,
    RunnerInstallationService,
    RunnerNotFoundError,
    RunnerPermissionError,
    RunnerServiceError,
    RunnerTransitionError,
    require_runner_enabled,
)
from .throttles import (
    RunnerMutationThrottle,
    RunnerReadThrottle,
    RunnerUserMutationThrottle,
    RunnerUserReadThrottle,
)


def runner_error_response(error: RunnerServiceError) -> Response:
    if isinstance(error, RunnerDisabledError):
        response_status = status.HTTP_404_NOT_FOUND
    elif isinstance(error, RunnerNotFoundError):
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


def audit_context_from_request(request) -> RunnerAuditContext:
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_request_id if RunnerAuditContext.is_valid_request_id(supplied_request_id) else str(uuid4())

    remote_addr = request.META.get("REMOTE_ADDR")
    try:
        source_ip = str(ip_address(remote_addr)) if remote_addr else None
    except ValueError:
        source_ip = None

    user_agent = "".join(character for character in request.headers.get("User-Agent", "") if character.isprintable())
    return RunnerAuditContext(
        request_id=request_id,
        source_ip=source_ip,
        user_agent=user_agent[:512],
    )


class RunnerBaseEndpoint(BaseAPIView):
    def get_throttles(self):
        throttle_classes = (
            [RunnerUserReadThrottle, RunnerReadThrottle]
            if self.request.method in {"GET", "HEAD", "OPTIONS"}
            else [RunnerUserMutationThrottle, RunnerMutationThrottle]
        )
        return [throttle() for throttle in throttle_classes]


class RunnerInstallationEndpoint(RunnerBaseEndpoint):
    @runner_enabled_endpoint
    def get(self, request, slug):
        try:
            workspace = RunnerInstallationService.resolve_for_admin(
                workspace_slug=slug,
                actor=request.user,
            )
            installation = RunnerInstallationService.get_for_admin(
                workspace=workspace,
                actor=request.user,
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return installation_response(installation)

    @runner_enabled_endpoint
    def post(self, request, slug):
        try:
            workspace = RunnerInstallationService.resolve_for_admin(
                workspace_slug=slug,
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
                audit_context=audit_context_from_request(request),
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return installation_response(result.installation, response_status=response_status)


class RunnerInstallationSuspendEndpoint(RunnerBaseEndpoint):
    @runner_enabled_endpoint
    def post(self, request, slug):
        try:
            workspace = RunnerInstallationService.resolve_for_admin(
                workspace_slug=slug,
                actor=request.user,
            )
            result = RunnerInstallationService.suspend(
                workspace=workspace,
                actor=request.user,
                audit_context=audit_context_from_request(request),
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return installation_response(result.installation)


class RunnerInstallationRevokeEndpoint(RunnerBaseEndpoint):
    @runner_enabled_endpoint
    def post(self, request, slug):
        try:
            workspace = RunnerInstallationService.resolve_for_admin(
                workspace_slug=slug,
                actor=request.user,
            )
            result = RunnerInstallationService.revoke(
                workspace=workspace,
                actor=request.user,
                audit_context=audit_context_from_request(request),
            )
        except RunnerServiceError as error:
            return runner_error_response(error)
        return installation_response(result.installation)
