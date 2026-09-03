# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import secrets
from datetime import date, timedelta
from urllib.parse import urlencode
from uuid import UUID
import base64 as cursor_base64

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.authentication.utils.oauth_transaction import consume_oauth_transaction, start_oauth_transaction
from plane.db.models import Issue, IssueType, Workspace, WorkspaceMember
from plane.ext.capacity import (
    GoogleCalendarClient,
    GoogleCalendarError,
    calculate_workspace_capacity,
    decrypt_value,
    encrypt_value,
    validate_intervals,
    validate_weekly_schedule,
)
from plane.ext.capacity.schedules import validate_timezone
from plane.ext.capacity.cache import clear_credential_cache, clear_selection_cache
from plane.ext.capacity.throttles import CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle
from plane.ext.models import (
    CapacityAuditEvent,
    GoogleCalendarCredential,
    TrainerCalendarSelection,
    TrainerProfile,
    TrainerScheduleException,
    WorkshopSchedule,
)
from plane.ext.services import ensure_workspace_workshop_type
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.permissions import ROLE, allow_permission

OAUTH_SESSION_KEY = "google_calendar_oauth"
CALENDAR_SCOPES = {
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events.freebusy",
}
EMAIL_SCOPE_ALIASES = {
    "email",
    "https://www.googleapis.com/auth/userinfo.email",
}
REQUIRED_CALENDAR_SCOPES = CALENDAR_SCOPES - {"email"}

logger = logging.getLogger(__name__)


def _parse_granted_scopes(scope: object) -> set[str]:
    return set(scope.split()) if isinstance(scope, str) else set()


def _has_required_calendar_scopes(granted: set[str]) -> bool:
    return REQUIRED_CALENDAR_SCOPES.issubset(granted) and not EMAIL_SCOPE_ALIASES.isdisjoint(granted)


def _audit(request, *, workspace_id, action, trainer_id=None, issue_id=None, metadata=None):
    CapacityAuditEvent.objects.create(
        workspace_id=workspace_id,
        actor_id=request.user.id,
        trainer_id=trainer_id,
        issue_id=issue_id,
        action=action,
        metadata=metadata or {},
    )


def _disabled():
    if settings.GOOGLE_CALENDAR_CAPACITY_ENABLED:
        return None
    return Response({"error": "Google Calendar capacity is disabled."}, status=status.HTTP_404_NOT_FOUND)


def _google_client():
    client_id, client_secret = get_configuration_value(
        [
            {"key": "GOOGLE_CLIENT_ID", "default": ""},
            {"key": "GOOGLE_CLIENT_SECRET", "default": ""},
        ]
    )
    if not client_id or not client_secret:
        raise GoogleCalendarError("not_configured")
    return GoogleCalendarClient(client_id=client_id, client_secret=client_secret), client_id


def _profile_payload(profile):
    try:
        selection = profile.calendar_selection
        connection_status = selection.credential.status
    except ObjectDoesNotExist:
        connection_status = "not_connected"
    return {
        "id": str(profile.id),
        "user_id": str(profile.user_id),
        "display_name": profile.user.display_name,
        "status": profile.status,
        "timezone": profile.timezone,
        "weekly_schedule": profile.weekly_schedule,
        "schedule_revision": profile.schedule_revision,
        "connection_status": connection_status,
        "exceptions": [
            {"date": item.local_date.isoformat(), "mode": item.mode, "intervals": item.intervals}
            for item in profile.schedule_exceptions.all()
        ],
    }


class TrainerSelfEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        profile = (
            TrainerProfile.objects.filter(workspace__slug=slug, user=request.user)
            .select_related("user")
            .prefetch_related("schedule_exceptions", "calendar_selection__credential")
            .first()
        )
        return Response(_profile_payload(profile) if profile else None)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def post(self, request, slug):
        if response := _disabled():
            return response
        workspace = Workspace.objects.get(slug=slug)
        profile, _ = TrainerProfile.objects.get_or_create(
            workspace=workspace,
            user=request.user,
            defaults={"timezone": request.user.user_timezone},
        )
        profile.status = TrainerProfile.Status.ACTIVE
        profile.save(update_fields=["status", "updated_at"])
        _audit(
            request,
            workspace_id=workspace.id,
            trainer_id=profile.user_id,
            action=CapacityAuditEvent.Action.TRAINER_ACTIVATED,
        )
        ensure_workspace_workshop_type(workspace)
        profile = (
            TrainerProfile.objects.prefetch_related("schedule_exceptions").select_related("user").get(pk=profile.pk)
        )
        return Response(_profile_payload(profile), status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def delete(self, request, slug):
        if response := _disabled():
            return response
        profile = get_object_or_404(TrainerProfile, workspace__slug=slug, user=request.user)
        profile.status = TrainerProfile.Status.SUSPENDED
        profile.save(update_fields=["status", "updated_at"])
        _audit(
            request,
            workspace_id=profile.workspace_id,
            trainer_id=profile.user_id,
            action=CapacityAuditEvent.Action.TRAINER_SUSPENDED,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrainerListEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        profiles = (
            TrainerProfile.objects.filter(workspace__slug=slug)
            .select_related("user")
            .prefetch_related("schedule_exceptions", "calendar_selection__credential")
        )
        cursor = request.query_params.get("cursor")
        if cursor:
            try:
                cursor_id = UUID(cursor_base64.urlsafe_b64decode(cursor.encode()).decode())
            except (binascii.Error, ValueError, UnicodeDecodeError):
                return Response({"error": "Invalid trainer cursor."}, status=400)
            profiles = profiles.filter(id__gt=cursor_id)
        rows = list(profiles.order_by("id")[:26])
        next_cursor = None
        if len(rows) > 25:
            rows = rows[:25]
            next_cursor = cursor_base64.urlsafe_b64encode(str(rows[-1].id).encode()).decode()
        return Response({"results": [_profile_payload(profile) for profile in rows], "next_cursor": next_cursor})


class TrainerScheduleEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    def _profile(self, slug, user_id):
        return get_object_or_404(
            TrainerProfile.objects.select_related("user").prefetch_related("schedule_exceptions"),
            workspace__slug=slug,
            user_id=user_id,
        )

    def _may_edit(self, request, profile):
        return (
            request.user.id == profile.user_id
            or WorkspaceMember.objects.filter(
                workspace=profile.workspace, member=request.user, role=ROLE.ADMIN.value, is_active=True
            ).exists()
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug, user_id):
        if response := _disabled():
            return response
        return Response(_profile_payload(self._profile(slug, user_id)))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def patch(self, request, slug, user_id):
        if response := _disabled():
            return response
        profile = self._profile(slug, user_id)
        if not self._may_edit(request, profile):
            return Response({"error": "You cannot edit this trainer."}, status=status.HTTP_403_FORBIDDEN)
        try:
            supplied_revision = int(request.data.get("schedule_revision"))
        except (TypeError, ValueError):
            return Response({"error": "schedule_revision is required."}, status=400)
        locked_profile = TrainerProfile.objects.select_for_update().get(pk=profile.pk)
        if supplied_revision != locked_profile.schedule_revision:
            return Response(
                {"error": "This schedule changed after you opened it.", "current": _profile_payload(profile)},
                status=status.HTTP_409_CONFLICT,
            )
        profile = locked_profile
        if "timezone" in request.data:
            profile.timezone = validate_timezone(request.data["timezone"])
        if "weekly_schedule" in request.data:
            profile.weekly_schedule = validate_weekly_schedule(request.data["weekly_schedule"])
        if "status" in request.data:
            if not WorkspaceMember.objects.filter(
                workspace=profile.workspace, member=request.user, role=ROLE.ADMIN.value, is_active=True
            ).exists():
                return Response({"error": "Only an administrator may change trainer status."}, status=403)
            if request.data["status"] not in TrainerProfile.Status.values:
                return Response({"error": "Invalid trainer status."}, status=400)
            profile.status = request.data["status"]
        profile.schedule_revision += 1
        profile.save()
        if "exceptions" in request.data:
            exceptions = request.data["exceptions"]
            if not isinstance(exceptions, list) or len(exceptions) > 366:
                raise ValidationError({"error": "Invalid schedule exceptions."})
            rows = []
            seen = set()
            for item in exceptions:
                try:
                    local_date = date.fromisoformat(item["date"])
                    mode = item["mode"]
                except (KeyError, TypeError, ValueError):
                    raise ValidationError({"error": "Invalid schedule exception."})
                if local_date in seen or mode not in TrainerScheduleException.Mode.values:
                    raise ValidationError({"error": "Invalid schedule exception."})
                seen.add(local_date)
                intervals = (
                    []
                    if mode == TrainerScheduleException.Mode.UNAVAILABLE
                    else validate_intervals(item.get("intervals", []))
                )
                rows.append(
                    TrainerScheduleException(trainer=profile, local_date=local_date, mode=mode, intervals=intervals)
                )
            TrainerScheduleException.objects.filter(trainer=profile).delete()
            TrainerScheduleException.objects.bulk_create(rows)
        _audit(
            request,
            workspace_id=profile.workspace_id,
            trainer_id=profile.user_id,
            action=CapacityAuditEvent.Action.SCHEDULE_UPDATED,
            metadata={"exception_count": len(request.data.get("exceptions", profile.schedule_exceptions.all()))},
        )
        return Response(_profile_payload(self._profile(slug, user_id)))


class GoogleCalendarStartEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        if response := _disabled():
            return response
        trainer = get_object_or_404(TrainerProfile, workspace__slug=slug, user=request.user, status="active")
        try:
            _, client_id = _google_client()
        except GoogleCalendarError:
            return Response({"error": "Google Calendar is not configured."}, status=503)
        redirect_uri = request.build_absolute_uri("/auth/google/calendar/callback/")
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = start_oauth_transaction(
            request, OAUTH_SESSION_KEY, host=request.get_host(), next_path=f"/{slug}/capacity"
        )
        request.session[OAUTH_SESSION_KEY].update(
            {"trainer_id": str(trainer.id), "workspace_slug": slug, "code_verifier": verifier}
        )
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(sorted(CALENDAR_SCOPES)),
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return Response({"authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"})


class GoogleCalendarCallbackEndpoint(BaseAPIView):
    @transaction.atomic
    def get(self, request):
        transaction_data, valid = consume_oauth_transaction(request, OAUTH_SESSION_KEY, request.GET.get("state"))
        slug = transaction_data.get("workspace_slug", "")
        failure = f"/{slug}/capacity?google=failed"
        if not valid or transaction_data.get("host") != request.get_host() or not request.GET.get("code"):
            return HttpResponseRedirect(failure)
        trainer = TrainerProfile.objects.filter(
            pk=transaction_data.get("trainer_id"), workspace__slug=slug, user=request.user, status="active"
        ).first()
        if trainer is None:
            return HttpResponseRedirect(failure)
        redirect_uri = request.build_absolute_uri("/auth/google/calendar/callback/")
        try:
            client, _ = _google_client()
            token = client.exchange_code(
                code=request.GET["code"], redirect_uri=redirect_uri, code_verifier=transaction_data["code_verifier"]
            )
            granted = _parse_granted_scopes(token.get("scope"))
            if not _has_required_calendar_scopes(granted):
                raise GoogleCalendarError("missing_scopes")
            userinfo = client.userinfo(token["access_token"])
            existing = GoogleCalendarCredential.objects.filter(user=request.user, google_subject=userinfo["id"]).first()
            refresh_token = token.get("refresh_token") or (
                decrypt_value(existing.encrypted_refresh_token, existing.encryption_key_id) if existing else ""
            )
            if not refresh_token:
                raise GoogleCalendarError("missing_refresh_token")
            encrypted, key_id = encrypt_value(refresh_token)
            credential, _ = GoogleCalendarCredential.objects.update_or_create(
                user=request.user,
                google_subject=userinfo["id"],
                defaults={
                    "encrypted_refresh_token": encrypted,
                    "encryption_key_id": key_id,
                    "granted_scopes": sorted(granted),
                    "status": GoogleCalendarCredential.Status.CONNECTED,
                    "last_error_code": "",
                },
            )
            TrainerCalendarSelection.objects.update_or_create(trainer=trainer, defaults={"credential": credential})
            _audit(
                request,
                workspace_id=trainer.workspace_id,
                trainer_id=trainer.user_id,
                action=CapacityAuditEvent.Action.GOOGLE_CONNECTED,
            )
        except GoogleCalendarError as exc:
            error_code = "missing_scopes" if exc.code == "missing_scopes" else "google_calendar_error"
            logger.warning(
                "Google Calendar OAuth callback failed",
                extra={"error_code": error_code},
            )
            return HttpResponseRedirect(failure)
        except (KeyError, ValueError):
            logger.warning(
                "Google Calendar OAuth callback returned an invalid token response",
                extra={"error_code": "invalid_token_response"},
            )
            return HttpResponseRedirect(failure)
        return HttpResponseRedirect(f"/{slug}/capacity?google=connected")


class GoogleCalendarsEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    def _selection(self, request, slug):
        return get_object_or_404(
            TrainerCalendarSelection.objects.select_related("credential", "trainer"),
            trainer__workspace__slug=slug,
            trainer__user=request.user,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        selection = self._selection(request, slug)
        try:
            calendars = _google_client()[0].list_calendars(selection.credential)
        except GoogleCalendarError as exc:
            return Response({"error": exc.code}, status=503)
        selected = set(selection.calendar_id_hashes)
        for calendar in calendars:
            calendar["selected"] = TrainerCalendarSelection.calendar_hash(calendar["id"]) in selected
        return Response({"calendars": calendars, "selection_revision": selection.revision})

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def put(self, request, slug):
        if response := _disabled():
            return response
        selection = self._selection(request, slug)
        calendar_ids = request.data.get("calendar_ids")
        try:
            supplied_revision = int(request.data.get("selection_revision"))
        except (TypeError, ValueError):
            return Response({"error": "selection_revision is required."}, status=400)
        selection = TrainerCalendarSelection.objects.select_for_update().get(pk=selection.pk)
        if supplied_revision != selection.revision:
            return Response(
                {"error": "Calendar selection changed after you opened it.", "selection_revision": selection.revision},
                status=status.HTTP_409_CONFLICT,
            )
        if (
            not isinstance(calendar_ids, list)
            or not 1 <= len(calendar_ids) <= 50
            or not all(isinstance(value, str) and 0 < len(value) <= 1024 for value in calendar_ids)
        ):
            return Response({"error": "Select between one and 50 calendars."}, status=400)
        try:
            allowed = {item["id"] for item in _google_client()[0].list_calendars(selection.credential)}
        except GoogleCalendarError as exc:
            return Response({"error": exc.code}, status=503)
        if not set(calendar_ids).issubset(allowed):
            return Response({"error": "A selected calendar is unavailable."}, status=400)
        encrypted = [encrypt_value(value)[0] for value in sorted(set(calendar_ids))]
        selection.encrypted_calendar_ids = encrypted
        selection.calendar_id_hashes = [
            TrainerCalendarSelection.calendar_hash(value) for value in sorted(set(calendar_ids))
        ]
        selection.revision += 1
        selection.save(update_fields=["encrypted_calendar_ids", "calendar_id_hashes", "revision", "updated_at"])
        _audit(
            request,
            workspace_id=selection.trainer.workspace_id,
            trainer_id=selection.trainer.user_id,
            action=CapacityAuditEvent.Action.CALENDARS_UPDATED,
            metadata={"calendar_count": len(encrypted), "revision": selection.revision},
        )
        return Response({"selected": len(encrypted), "revision": selection.revision})

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def delete(self, request, slug):
        if response := _disabled():
            return response
        selection = self._selection(request, slug)
        credential = selection.credential
        last_selection = not credential.trainer_selections.exclude(pk=selection.pk).exists()
        if last_selection and request.query_params.get("force_local") != "true":
            try:
                _google_client()[0].revoke(credential)
            except GoogleCalendarError:
                return Response(
                    {
                        "error": "revocation_failed",
                        "can_force_local_disconnect": True,
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        clear_selection_cache(selection.id)
        # Disconnect is a privacy boundary: erase selected calendar identifiers
        # rather than retaining them through the application's soft-delete layer.
        selection.delete(soft=False)
        if last_selection:
            clear_credential_cache(credential.id)
            credential.delete(soft=False)
        _audit(
            request,
            workspace_id=selection.trainer.workspace_id,
            trainer_id=selection.trainer.user_id,
            action=CapacityAuditEvent.Action.GOOGLE_DISCONNECTED,
            metadata={"forced_local": request.query_params.get("force_local") == "true"},
        )
        return Response(status=204)


class WorkspaceCapacityEndpoint(BaseAPIView):
    throttle_classes = [CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        start, end = parse_datetime(request.GET.get("from", "")), parse_datetime(request.GET.get("to", ""))
        if not start or not end or timezone.is_naive(start) or timezone.is_naive(end) or not start < end:
            return Response({"error": "from and to must be timezone-aware RFC3339 values."}, status=400)
        if end - start > timedelta(days=14):
            return Response({"error": "Capacity range may not exceed 14 days."}, status=400)
        trainer_ids = [value for value in request.GET.get("trainer_ids", "").split(",") if value]
        workspace = Workspace.objects.get(slug=slug)
        if len(trainer_ids) > 25:
            return Response({"error": "Select at most 25 trainers."}, status=400)
        try:
            trainer_ids = [str(UUID(value)) for value in trainer_ids]
        except ValueError:
            return Response({"error": "trainer_ids must contain valid UUIDs."}, status=400)
        if not trainer_ids:
            active_count = TrainerProfile.objects.filter(workspace=workspace, status="active").count()
            if active_count > 25:
                return Response(
                    {"error": "This workspace has more than 25 trainers; select trainer_ids explicitly."},
                    status=400,
                )
        return Response(
            {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "trainers": calculate_workspace_capacity(
                    workspace=workspace, viewer=request.user, start=start, end=end, trainer_ids=trainer_ids
                ),
            }
        )


class WorkshopScheduleEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    def _issue(self, slug, project_id, issue_id):
        return get_object_or_404(Issue, workspace__slug=slug, project_id=project_id, pk=issue_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        if response := _disabled():
            return response
        schedule = get_object_or_404(WorkshopSchedule, issue=self._issue(slug, project_id, issue_id))
        return Response(self._payload(schedule))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    @transaction.atomic
    def put(self, request, slug, project_id, issue_id):
        if response := _disabled():
            return response
        issue = self._issue(slug, project_id, issue_id)
        if not issue.type_id or issue.type.system_key != IssueType.SystemKey.WORKSHOP:
            return Response({"error": "Only Workshop work items may be scheduled."}, status=400)
        starts_at, ends_at = (
            parse_datetime(request.data.get("starts_at", "")),
            parse_datetime(request.data.get("ends_at", "")),
        )
        if (
            not starts_at
            or not ends_at
            or timezone.is_naive(starts_at)
            or timezone.is_naive(ends_at)
            or starts_at >= ends_at
        ):
            return Response({"error": "A valid timezone-aware workshop range is required."}, status=400)
        if ends_at - starts_at > timedelta(days=7):
            return Response({"error": "A Workshop may not exceed seven days."}, status=400)
        assignees = set(issue.issue_assignee.values_list("assignee_id", flat=True))
        if not assignees:
            return Response({"error": "A Workshop requires at least one trainer."}, status=400)
        active_trainers = set(
            TrainerProfile.objects.filter(
                workspace=issue.workspace, user_id__in=assignees, status="active"
            ).values_list("user_id", flat=True)
        )
        if assignees - active_trainers:
            return Response({"error": "Every Workshop assignee must be an active trainer."}, status=400)
        values = {}
        for field in ("preparation_minutes", "travel_before_minutes", "travel_after_minutes"):
            try:
                value = int(request.data.get(field, 0))
            except (TypeError, ValueError):
                return Response({"error": f"{field} must be an integer."}, status=400)
            if not 0 <= value <= 1440:
                return Response({"error": f"{field} must be between 0 and 1440."}, status=400)
            values[field] = value
        schedule, _ = WorkshopSchedule.objects.update_or_create(
            issue=issue, defaults={"starts_at": starts_at, "ends_at": ends_at, **values}
        )
        _audit(
            request,
            workspace_id=issue.workspace_id,
            issue_id=issue.id,
            action=CapacityAuditEvent.Action.WORKSHOP_UPDATED,
        )
        return Response(self._payload(schedule))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    @transaction.atomic
    def delete(self, request, slug, project_id, issue_id):
        if response := _disabled():
            return response
        # A schedule can be recreated later; hard deletion avoids the one-to-one
        # uniqueness conflict that a soft-deleted row would otherwise retain.
        issue = self._issue(slug, project_id, issue_id)
        WorkshopSchedule.objects.filter(issue=issue).delete(soft=False)
        _audit(
            request,
            workspace_id=issue.workspace_id,
            issue_id=issue.id,
            action=CapacityAuditEvent.Action.WORKSHOP_REMOVED,
        )
        return Response(status=204)

    @staticmethod
    def _payload(schedule):
        return {
            "issue_id": str(schedule.issue_id),
            "starts_at": schedule.starts_at.isoformat(),
            "ends_at": schedule.ends_at.isoformat(),
            "preparation_minutes": schedule.preparation_minutes,
            "travel_before_minutes": schedule.travel_before_minutes,
            "travel_after_minutes": schedule.travel_after_minutes,
        }
