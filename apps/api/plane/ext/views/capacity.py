# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

import base64
import binascii
import json
import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID
import base64 as cursor_base64

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import CsrfEnforcedSessionAuthentication
from plane.authentication.utils.oauth_transaction import consume_oauth_transaction, start_oauth_transaction
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueAssignee, IssueType, ProjectMember, Workspace, WorkspaceMember
from plane.utils.host import base_host
from plane.ext.capacity import (
    GoogleCalendarClient,
    GoogleCalendarError,
    calculate_workspace_capacity,
    decrypt_value,
    encrypt_value,
    validate_weekly_schedule,
)
from plane.ext.capacity.training_events import EVENTS_SCOPE
from plane.ext.capacity.booking import booking_preflight, snapshot_error
from plane.ext.capacity.timezones import trainer_timezone
from plane.ext.capacity.cache import clear_credential_cache, clear_selection_cache
from plane.ext.capacity.throttles import CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle
from plane.ext.models import (
    CapacityAuditEvent,
    GoogleCalendarCredential,
    GoogleTrainingRule,
    TrainerCalendarSelection,
    TrainerProfile,
    WorkshopBookingOperation,
    WorkshopPlanDraft,
    WorkshopPlanHold,
    WorkshopSchedule,
    WorkshopSession,
    WorkshopSessionCalendarEvent,
)
from plane.ext.capacity.calendar_sync import (
    enqueue,
    mark_sessions_absent,
    reconcile_session,
    writeback_enabled,
)
from plane.ext.services.workshop_properties import delivering_trainer_ids
from plane.ext.services.workshop_checklist import backfill_target_dates
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

# Writing a workshop into the shared training calendar. Deliberately its own
# scope set rather than an addition to the trainer's: a coordinator who connects
# only to create entries has no use for free/busy or the calendar list, and
# asking for permissions a feature does not exercise is the habit this subsystem
# refuses. `calendar.app.created` cannot serve here -- the training calendar
# already exists and was not created by this application.
CALENDAR_WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.events"
WRITER_SCOPES = {"openid", "email", CALENDAR_WRITE_SCOPE}

logger = logging.getLogger(__name__)


def _parse_granted_scopes(scope: object) -> set[str]:
    return set(scope.split()) if isinstance(scope, str) else set()


def _has_required_calendar_scopes(granted: set[str]) -> bool:
    return REQUIRED_CALENDAR_SCOPES.issubset(granted) and not EMAIL_SCOPE_ALIASES.isdisjoint(granted)


def _has_required_writer_scopes(granted: set[str]) -> bool:
    return CALENDAR_WRITE_SCOPE in granted and not EMAIL_SCOPE_ALIASES.isdisjoint(granted)


def _select_primary_calendar(client, selection, *, created: bool) -> None:
    if selection.calendar_id_hashes:
        return
    try:
        primary = next((item for item in client.list_calendars(selection.credential) if item["primary"]), None)
        if primary is None:
            raise GoogleCalendarError("primary_calendar_missing")
        encrypted, key_id = encrypt_value(primary["id"])
        if key_id != selection.credential.encryption_key_id:
            raise GoogleCalendarError("calendar_encryption_key_mismatch")
        selection.encrypted_calendar_ids = [encrypted]
        selection.calendar_id_hashes = [TrainerCalendarSelection.calendar_hash(primary["id"])]
        if not created:
            selection.revision += 1
        selection.save(update_fields=["encrypted_calendar_ids", "calendar_id_hashes", "revision", "updated_at"])
    except (GoogleCalendarError, KeyError, ValueError):
        logger.warning(
            "Google Calendar primary calendar was not selected automatically",
            extra={"error_code": "primary_calendar_autoselect_failed"},
        )


def _audit(request, *, workspace_id, action, trainer_id=None, issue_id=None, metadata=None):
    CapacityAuditEvent.objects.create(
        workspace_id=workspace_id,
        actor_id=request.user.id,
        trainer_id=trainer_id,
        issue_id=issue_id,
        action=action,
        metadata=metadata or {},
    )


def _is_workspace_admin(request, slug) -> bool:
    return WorkspaceMember.objects.filter(
        workspace__slug=slug, member=request.user, role=ROLE.ADMIN.value, is_active=True
    ).exists()


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
        "timezone": trainer_timezone(profile)[0],
        "timezone_source": trainer_timezone(profile)[1],
        "weekly_schedule": profile.weekly_schedule,
        "schedule_revision": profile.schedule_revision,
        "connection_status": connection_status,
        "training_events_enabled": bool(connection_status != "not_connected" and selection.training_events_enabled),
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
            .prefetch_related("calendar_selection__credential")
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
        # Becoming a trainer no longer puts the Workshop type into every project.
        # Which projects hold training is a decision each project makes itself.
        profile = TrainerProfile.objects.select_related("user").get(pk=profile.pk)
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
            .prefetch_related("calendar_selection__credential")
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
            TrainerProfile.objects.select_related("user"),
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
        if "exceptions" in request.data:
            return Response(
                {"error": "Schedule exceptions are no longer supported. Block that time in Google Calendar."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
        # Older clients may still submit timezone; booking hours now follow the
        # connected primary calendar, with the user profile as fallback.
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
        _audit(
            request,
            workspace_id=profile.workspace_id,
            trainer_id=profile.user_id,
            action=CapacityAuditEvent.Action.SCHEDULE_UPDATED,
            metadata={},
        )
        return Response(_profile_payload(self._profile(slug, user_id)))


class GoogleCalendarStartEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        if response := _disabled():
            return response
        # Two connections come through here, and only one of them belongs to a
        # trainer. The coordinator who writes workshops into the shared calendar
        # need not be a trainer at all, so the writer variant must not be gated
        # on a trainer profile -- doing so would lock out exactly the person the
        # feature exists for.
        writing = request.data.get("calendar_writer") is True
        trainer = None
        rule = None
        if writing:
            if not _is_workspace_admin(request, slug):
                return Response({"error": "Only workspace administrators connect a writing account."}, status=403)
            rule = get_object_or_404(GoogleTrainingRule, workspace__slug=slug, id=request.data.get("rule_id"))
        else:
            trainer = get_object_or_404(TrainerProfile, workspace__slug=slug, user=request.user, status="active")
        try:
            _, client_id = _google_client()
        except GoogleCalendarError:
            return Response({"error": "Google Calendar is not configured."}, status=503)
        redirect_uri = request.build_absolute_uri("/auth/google/calendar/callback/")
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        next_path = f"/{slug}/capacity/team" if writing else f"/{slug}/capacity"
        state = start_oauth_transaction(request, OAUTH_SESSION_KEY, host=request.get_host(), next_path=next_path)
        request.session[OAUTH_SESSION_KEY].update(
            {
                "trainer_id": str(trainer.id) if trainer else "",
                "workspace_slug": slug,
                "code_verifier": verifier,
                "training_events": request.data.get("training_events") is True,
                "calendar_writer": writing,
                "rule_id": str(rule.id) if rule else "",
            }
        )
        if writing:
            requested_scopes = WRITER_SCOPES
        else:
            requested_scopes = CALENDAR_SCOPES | (
                {EVENTS_SCOPE} if request.data.get("training_events") is True else set()
            )
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(sorted(requested_scopes)),
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
        writing = transaction_data.get("calendar_writer") is True
        landing = f"/{slug}/capacity/team" if writing else f"/{slug}/capacity"
        failure = f"{landing}?google=failed"
        if not valid or transaction_data.get("host") != request.get_host() or not request.GET.get("code"):
            return HttpResponseRedirect(failure)
        trainer = None
        rule = None
        if writing:
            # Re-checked here rather than trusted from the session: the
            # authorization happened before the round trip to Google, and an
            # administrator can lose the role while it is in flight.
            if not _is_workspace_admin(request, slug):
                return HttpResponseRedirect(failure)
            rule = GoogleTrainingRule.objects.filter(pk=transaction_data.get("rule_id"), workspace__slug=slug).first()
            if rule is None:
                return HttpResponseRedirect(failure)
        else:
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
            if writing:
                if not _has_required_writer_scopes(granted):
                    raise GoogleCalendarError("missing_scopes")
            else:
                if not _has_required_calendar_scopes(granted):
                    raise GoogleCalendarError("missing_scopes")
                if transaction_data.get("training_events") and EVENTS_SCOPE not in granted:
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
                    "encrypted_google_email": encrypt_value(userinfo["email"].casefold())[0],
                    "encrypted_refresh_token": encrypted,
                    "encryption_key_id": key_id,
                    "granted_scopes": sorted(granted),
                    "status": GoogleCalendarCredential.Status.CONNECTED,
                    "last_error_code": "",
                },
            )
            if writing:
                rule.writer_credential = credential
                rule.save(update_fields=["writer_credential", "updated_at"])
                _audit(
                    request,
                    workspace_id=rule.workspace_id,
                    action=CapacityAuditEvent.Action.CALENDAR_WRITER_CONNECTED,
                    metadata={"rule_id": str(rule.id)},
                )
            else:
                selection, created = TrainerCalendarSelection.objects.update_or_create(
                    trainer=trainer, defaults={"credential": credential}
                )
                if transaction_data.get("training_events"):
                    selection.training_events_enabled = True
                    selection.revision += 1
                    selection.save(update_fields=["training_events_enabled", "revision", "updated_at"])
                _select_primary_calendar(client, selection, created=created)
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
        return HttpResponseRedirect(f"{landing}?google=connected")


def _training_calendar_ids(workspace_id):
    """The calendars this workspace's rules already read as training.

    A trainer who also picks one of these as a blocking calendar blocks their own
    time with every training the company runs, not only their own -- the rule
    calendar carries everybody's. Recognition already blocks the ones that are
    theirs, from their own invitations, so the answer is to keep these out of the
    blocking list rather than to explain the arithmetic afterwards.
    """
    ids = set()
    for rule in GoogleTrainingRule.objects.filter(workspace_id=workspace_id):
        try:
            ids.add(decrypt_value(rule.encrypted_calendar_id, rule.encryption_key_id))
        except Exception:
            # A rule encrypted under a key this instance no longer has is one we
            # cannot compare against. Better to leave the calendar selectable
            # than to fail the whole listing over it.
            continue
    return ids


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
        training = _training_calendar_ids(selection.trainer.workspace_id)
        for calendar in calendars:
            calendar["selected"] = TrainerCalendarSelection.calendar_hash(calendar["id"]) in selected
            calendar["is_training_calendar"] = calendar["id"] in training
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
        if set(calendar_ids) & _training_calendar_ids(selection.trainer.workspace_id):
            return Response(
                {
                    "error": (
                        "A shared training calendar cannot block your time: it carries everybody's training, "
                        "not only yours. Your own trainings are already recognized from your invitations."
                    ),
                    "code": "training_calendar_not_blocking",
                },
                status=400,
            )
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


class WorkshopCalendarResyncEndpoint(BaseAPIView):
    """Try the shared calendar again now, rather than at the next sweep.

    Exists because the usual reason a row is stuck is something a person just
    fixed -- a reconnected writing account, a trainer who finally connected
    Google -- and asking them to wait out a backoff they cannot see is how a
    feature acquires a reputation for not working.

    It clears the backoff rather than calling Google inline: the worker is still
    the only thing that writes, so one impatient administrator cannot turn a
    rate limit into a storm of retries.
    """

    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    @transaction.atomic
    def post(self, request, slug, project_id, issue_id):
        if response := _disabled():
            return response
        if not writeback_enabled():
            return Response({"error": "Calendar write-back is disabled."}, status=404)
        issue = get_object_or_404(
            Issue,
            pk=issue_id,
            project_id=project_id,
            workspace__slug=slug,
            project__project_projectmember__member=request.user,
        )
        session_ids = list(WorkshopSession.objects.filter(schedule__issue=issue).values_list("id", flat=True))
        rows = list(
            WorkshopSessionCalendarEvent.objects.select_for_update()
            .filter(source_session_id__in=session_ids)
            .exclude(synced_revision=F("revision"))
        )
        now = timezone.now()
        for row in rows:
            row.attempts = 0
            row.available_at = now
            # A blocked row is not retried by clearing a timer: its cause is a
            # fact about the world, and if that fact changed, re-planning is
            # what records the change. Leaving it blocked keeps the reason
            # visible instead of hiding it behind a spinner.
            if row.state in (
                WorkshopSessionCalendarEvent.State.FAILED,
                WorkshopSessionCalendarEvent.State.BLOCKED_NO_WRITER,
            ):
                row.state = WorkshopSessionCalendarEvent.State.PENDING
            row.save(update_fields=["attempts", "available_at", "state", "updated_at"])
        enqueue([row.id for row in rows if row.state == WorkshopSessionCalendarEvent.State.PENDING])
        return Response({"queued": sum(1 for row in rows if row.state == WorkshopSessionCalendarEvent.State.PENDING)})


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
                    workspace=workspace,
                    viewer=request.user,
                    start=start,
                    end=end,
                    trainer_ids=trainer_ids,
                    # Resolved here, where the request is, rather than inside the
                    # calculation: a title belongs to the trainer's calendar, so
                    # only an administrator or that trainer may read it.
                    may_read_titles=WorkspaceMember.objects.filter(
                        workspace=workspace, member=request.user, role=20, is_active=True
                    ).exists(),
                ),
            }
        )


def _issue_payload(issue):
    """Enough to name a work item in a picker and link to it."""
    return {
        "id": str(issue.id),
        "name": issue.name,
        "sequence_id": issue.sequence_id,
        "project_id": str(issue.project_id),
        "project_identifier": issue.project.identifier,
    }


def _last_plan_session(draft):
    session = draft.scheduled_sessions.order_by("-created_at").first()
    if not session:
        return None
    return {"id": str(session.id), "starts_at": session.starts_at.isoformat(), "ends_at": session.ends_at.isoformat()}


def _draft_payload(draft):
    now = timezone.now()
    hold = (
        draft.holds.filter(status=WorkshopPlanHold.Status.ACTIVE, expires_at__gt=now).select_related("trainer").first()
    )
    return {
        "id": str(draft.id),
        "title": draft.title,
        "duration_minutes": draft.duration_minutes,
        "preparation_minutes": draft.preparation_minutes,
        "travel_before_minutes": draft.travel_before_minutes,
        "travel_after_minutes": draft.travel_after_minutes,
        "trainer_ids": draft.trainer_ids,
        "issue": _issue_payload(draft.issue) if draft.issue_id else None,
        "revision": draft.revision,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
        "last_session": _last_plan_session(draft),
        "hold": _hold_payload(hold) if hold else None,
    }


def _hold_payload(hold):
    return {
        "id": str(hold.id),
        "trainer_id": str(hold.trainer_id),
        "trainer_name": hold.trainer.display_name,
        "workshop_starts_at": hold.workshop_starts_at.isoformat(),
        "workshop_ends_at": hold.workshop_ends_at.isoformat(),
        "blocked_starts_at": hold.blocked_starts_at.isoformat(),
        "blocked_ends_at": hold.blocked_ends_at.isoformat(),
        "expires_at": hold.expires_at.isoformat(),
        "status": hold.status,
    }


def _validate_draft(request, workspace):
    title = request.data.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 255:
        return None, Response({"error": "title must contain between 1 and 255 characters."}, status=400)
    values = {"title": title.strip()}
    for field, minimum, maximum in (
        ("duration_minutes", 15, 10080),
        ("preparation_minutes", 0, 1440),
        ("travel_before_minutes", 0, 1440),
        ("travel_after_minutes", 0, 1440),
    ):
        try:
            value = int(request.data.get(field, 0))
        except (TypeError, ValueError):
            return None, Response({"error": f"{field} must be an integer."}, status=400)
        if not minimum <= value <= maximum:
            return None, Response({"error": f"{field} must be between {minimum} and {maximum}."}, status=400)
        values[field] = value
    raw_trainer_ids = request.data.get("trainer_ids")
    if not isinstance(raw_trainer_ids, list) or not 1 <= len(raw_trainer_ids) <= 25:
        return None, Response({"error": "Select between 1 and 25 trainers."}, status=400)
    try:
        trainer_ids = sorted({str(UUID(str(value))) for value in raw_trainer_ids})
    except (TypeError, ValueError, AttributeError):
        return None, Response({"error": "trainer_ids must contain valid UUIDs."}, status=400)
    active_ids = set(
        TrainerProfile.objects.filter(workspace=workspace, status="active", user_id__in=trainer_ids).values_list(
            "user_id", flat=True
        )
    )
    if active_ids != {UUID(value) for value in trainer_ids}:
        return None, Response({"error": "Every selected trainer must be active in this workspace."}, status=400)
    values["trainer_ids"] = trainer_ids

    # The work item the plan is for. Absent and null are both "not attached yet",
    # which is a legitimate state -- a coordinator may be answering "could we fit
    # this at all?" before anyone has raised a Workshop for it.
    raw_issue_id = request.data.get("issue_id")
    if raw_issue_id in (None, ""):
        values["issue"] = None
        return values, None
    try:
        issue_id = UUID(str(raw_issue_id))
    except (TypeError, ValueError, AttributeError):
        return None, Response({"error": "issue_id must be a valid identifier."}, status=400)
    issue = Issue.objects.filter(workspace=workspace, pk=issue_id).select_related("type", "project").first()
    # Not found rather than forbidden for a work item in a project the requester
    # is not in: the alternative confirms that a given identifier exists.
    if (
        issue is None
        or not ProjectMember.objects.filter(
            project_id=issue.project_id, member=request.user, role__gte=ROLE.MEMBER.value, is_active=True
        ).exists()
    ):
        return None, Response({"error": "No such Workshop work item in this workspace."}, status=404)
    if not issue.type_id or issue.type.system_key != IssueType.SystemKey.WORKSHOP:
        return None, Response({"error": "Only Workshop work items can be planned."}, status=400)
    values["issue"] = issue
    return values, None


class WorkshopPlanDraftListEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        drafts = WorkshopPlanDraft.objects.filter(workspace__slug=slug, owner=request.user).select_related(
            "issue__project"
        )[:50]
        return Response({"results": [_draft_payload(draft) for draft in drafts]})

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def post(self, request, slug):
        if response := _disabled():
            return response
        workspace = Workspace.objects.get(slug=slug)
        # Each draft can carry a reservation, so an unbounded number of drafts is
        # an unbounded number of ways to take a trainer's time out of
        # circulation. The saved-plan list only ever showed fifty of them.
        if (
            WorkshopPlanDraft.objects.filter(workspace=workspace, owner=request.user).count()
            >= settings.CAPACITY_MAX_PLAN_DRAFTS_PER_USER
        ):
            return Response(
                {"error": ("You have as many saved plans as this workspace allows. Delete one you no longer need.")},
                status=status.HTTP_409_CONFLICT,
            )
        values, error = _validate_draft(request, workspace)
        if error:
            return error
        draft = WorkshopPlanDraft.objects.create(
            workspace=workspace, owner=request.user, created_by=request.user, updated_by=request.user, **values
        )
        _audit(
            request,
            workspace_id=workspace.id,
            action=CapacityAuditEvent.Action.PLAN_DRAFT_CREATED,
            metadata={"draft_id": str(draft.id)},
        )
        return Response(_draft_payload(draft), status=status.HTTP_201_CREATED)


class WorkshopPlanDraftDetailEndpoint(BaseAPIView):
    authentication_classes = [CsrfEnforcedSessionAuthentication]

    @staticmethod
    def _draft(request, slug, draft_id):
        return get_object_or_404(WorkshopPlanDraft, workspace__slug=slug, owner=request.user, pk=draft_id)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def put(self, request, slug, draft_id):
        if response := _disabled():
            return response
        draft = get_object_or_404(
            WorkshopPlanDraft.objects.select_for_update(), workspace__slug=slug, owner=request.user, pk=draft_id
        )
        try:
            revision = int(request.data.get("revision"))
        except (TypeError, ValueError):
            return Response({"error": "revision is required."}, status=400)
        if revision != draft.revision:
            return Response(
                {"error": "Draft changed after you opened it.", "revision": draft.revision},
                status=status.HTTP_409_CONFLICT,
            )
        if draft.holds.filter(status=WorkshopPlanHold.Status.ACTIVE, expires_at__gt=timezone.now()).exists():
            return Response({"error": "Release the active hold before editing this plan."}, status=409)
        values, error = _validate_draft(request, draft.workspace)
        if error:
            return error
        for field, value in values.items():
            setattr(draft, field, value)
        draft.revision += 1
        draft.updated_by = request.user
        draft.save()
        _audit(
            request,
            workspace_id=draft.workspace_id,
            action=CapacityAuditEvent.Action.PLAN_DRAFT_UPDATED,
            metadata={"draft_id": str(draft.id), "revision": draft.revision},
        )
        return Response(_draft_payload(draft))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def patch(self, request, slug, draft_id):
        if response := _disabled():
            return response
        draft = self._draft(request, slug, draft_id)
        if set(request.data) - {"title", "issue_id", "revision"}:
            return Response({"error": "Only title and issue_id may change while reserved."}, status=400)
        try:
            revision = int(request.data.get("revision"))
        except (TypeError, ValueError):
            return Response({"error": "revision is required."}, status=400)
        if revision != draft.revision:
            return Response({"error": "Draft changed after you opened it.", "revision": draft.revision}, status=409)
        from types import SimpleNamespace

        data = {
            field: getattr(draft, field)
            for field in (
                "title",
                "duration_minutes",
                "preparation_minutes",
                "travel_before_minutes",
                "travel_after_minutes",
                "trainer_ids",
            )
        }
        data["issue_id"] = str(draft.issue_id) if draft.issue_id else None
        data.update(request.data)
        values, error = _validate_draft(SimpleNamespace(data=data, user=request.user), draft.workspace)
        if error:
            return error
        draft.title, draft.issue = values["title"], values["issue"]
        draft.revision += 1
        draft.updated_by = request.user
        draft.save()
        _audit(
            request,
            workspace_id=draft.workspace_id,
            action=CapacityAuditEvent.Action.PLAN_DRAFT_UPDATED,
            metadata={"draft_id": str(draft.id), "revision": draft.revision},
        )
        return Response(_draft_payload(draft))

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def delete(self, request, slug, draft_id):
        if response := _disabled():
            return response
        draft = self._draft(request, slug, draft_id)
        draft.delete(soft=False)
        _audit(
            request,
            workspace_id=draft.workspace_id,
            action=CapacityAuditEvent.Action.PLAN_DRAFT_REMOVED,
            metadata={"draft_id": str(draft.id)},
        )
        return Response(status=204)


def _blocks_conflict(
    *,
    workspace,
    trainer,
    blocked_start,
    blocked_end,
    now,
    excluding_draft=None,
    excluding_hold=None,
    excluding_schedule=None,
):
    """
    Whether this trainer's complete block collides with anything already taken.

    Asked twice in the life of a plan and it must give the same answer both
    times: once when a hold is taken, and again up to seventy-two hours later
    when that hold becomes a session. Availability moves in between -- another
    coordinator holds the same afternoon, a workshop is scheduled directly on a
    work item -- so scheduling cannot assume the hold is still honest.

    `excluding_draft` skips the plan's own holds when taking a new one;
    `excluding_hold` skips the single hold being spent; `excluding_schedule`
    skips the workshop being rewritten, whose own sessions are about to be
    replaced and must not collide with their replacements.
    """
    holds = WorkshopPlanHold.objects.filter(
        workspace=workspace,
        trainer_id=trainer.user_id,
        status=WorkshopPlanHold.Status.ACTIVE,
        expires_at__gt=now,
        blocked_starts_at__lt=blocked_end,
        blocked_ends_at__gt=blocked_start,
    )
    if excluding_draft is not None:
        holds = holds.exclude(draft=excluding_draft)
    if excluding_hold is not None:
        holds = holds.exclude(pk=excluding_hold.pk)
    if holds.exists():
        return True

    # Bounded by time as well as by trainer. The buffers are per session and can
    # reach a day on each side, so the window is widened rather than dropped --
    # but without any bound this walked every session the trainer has ever had,
    # and it does so while the trainer row is locked, which makes scan time into
    # lock-hold time.
    sessions = WorkshopSession.objects.filter(
        schedule__workspace=workspace,
        trainers=trainer.user,
        starts_at__lt=blocked_end + timedelta(minutes=1440),
        ends_at__gt=blocked_start - timedelta(minutes=2880),
    ).distinct()
    if excluding_schedule is not None:
        sessions = sessions.exclude(schedule=excluding_schedule)
    return any(
        session.starts_at - timedelta(minutes=session.preparation_minutes + session.travel_before_minutes) < blocked_end
        and session.ends_at + timedelta(minutes=session.travel_after_minutes) > blocked_start
        for session in sessions
    )


def _schedule_conflict(*, issue, parsed_sessions, now):
    """The first collision in a proposed set of sessions, or None.

    Two questions, because they have different blast radii. Sessions in the
    submitted payload are checked against each other, which can only ever refuse
    a request somebody is making right now. They are then checked against other
    workshops and live holds, skipping this workshop's own stored sessions --
    those are about to be replaced, so colliding with them would make every edit
    impossible.
    """
    for position, session in enumerate(parsed_sessions):
        start = session["starts_at"] - timedelta(
            minutes=session["preparation_minutes"] + session["travel_before_minutes"]
        )
        end = session["ends_at"] + timedelta(minutes=session["travel_after_minutes"])
        for other_position, other in enumerate(parsed_sessions):
            if other_position >= position or not (session["trainer_ids"] & other["trainer_ids"]):
                continue
            other_start = other["starts_at"] - timedelta(
                minutes=other["preparation_minutes"] + other["travel_before_minutes"]
            )
            other_end = other["ends_at"] + timedelta(minutes=other["travel_after_minutes"])
            if other_start < end and other_end > start:
                return f"Sessions {other_position + 1} and {position + 1} put the same trainer in two places at once."

    schedule = WorkshopSchedule.objects.filter(issue=issue).first()
    trainers = {
        profile.user_id: profile
        for profile in TrainerProfile.objects.filter(
            workspace=issue.workspace,
            user_id__in={trainer_id for session in parsed_sessions for trainer_id in session["trainer_ids"]},
        ).select_related("user")
    }
    for position, session in enumerate(parsed_sessions):
        start = session["starts_at"] - timedelta(
            minutes=session["preparation_minutes"] + session["travel_before_minutes"]
        )
        end = session["ends_at"] + timedelta(minutes=session["travel_after_minutes"])
        for trainer_id in sorted(session["trainer_ids"]):
            trainer = trainers.get(trainer_id)
            if trainer is None:
                continue
            if _blocks_conflict(
                workspace=issue.workspace,
                trainer=trainer,
                blocked_start=start,
                blocked_end=end,
                now=now,
                excluding_schedule=schedule,
            ):
                return f"Session {position + 1} collides with something already booked for {trainer.user.display_name}."
    return None


class WorkshopPlanHoldEndpoint(BaseAPIView):
    """Reserving a trainer for seventy-two hours.

    Throttled with the ledger's own classes, deliberately sharing its budget.
    `booking_preflight` forces a fresh Google read *before* the conflict check,
    so a caller who only ever gets 409s still spends the quota the ledger
    throttle exists to protect -- leaving this endpoint unthrottled was a way
    around it.
    """

    authentication_classes = [CsrfEnforcedSessionAuthentication]
    throttle_classes = [CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle]

    @staticmethod
    def _draft(request, slug, draft_id):
        return get_object_or_404(
            WorkshopPlanDraft.objects.select_for_update(),
            workspace__slug=slug,
            owner=request.user,
            pk=draft_id,
        )

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @booking_preflight()
    @transaction.atomic
    def post(self, request, slug, draft_id):
        if response := _disabled():
            return response
        draft = self._draft(request, slug, draft_id)
        try:
            revision = int(request.data.get("revision"))
            trainer_id = UUID(str(request.data.get("trainer_id")))
        except (TypeError, ValueError, AttributeError):
            return Response({"error": "revision and a valid trainer_id are required."}, status=400)
        if revision != draft.revision:
            return Response(
                {"error": "Draft changed after you opened it.", "revision": draft.revision},
                status=status.HTTP_409_CONFLICT,
            )
        if str(trainer_id) not in draft.trainer_ids:
            return Response({"error": "The trainer is not eligible for this plan."}, status=400)
        workshop_start = parse_datetime(request.data.get("workshop_starts_at", ""))
        if not workshop_start or timezone.is_naive(workshop_start):
            return Response({"error": "A timezone-aware workshop_starts_at is required."}, status=400)
        workshop_end = workshop_start + timedelta(minutes=draft.duration_minutes)
        blocked_start = workshop_start - timedelta(minutes=draft.preparation_minutes + draft.travel_before_minutes)
        blocked_end = workshop_end + timedelta(minutes=draft.travel_after_minutes)
        # The block is checked against the trainer's real availability below, not
        # against a saved window: a plan is the same plan whichever week you view
        # it in. All that is required of the block itself is that it has not
        # already happened -- holding a trainer for last Tuesday reserves nothing.
        # One `now` for this and for every conflict query, so they cannot disagree
        # about where the present is.
        now = timezone.now()
        if blocked_start < now:
            return Response({"error": "The trainer block has already started."}, status=400)

        trainer = get_object_or_404(
            TrainerProfile.objects.select_for_update().select_related("user"),
            workspace=draft.workspace,
            user_id=trainer_id,
            status=TrainerProfile.Status.ACTIVE,
        )
        if response := snapshot_error(request, draft, trainer):
            return response
        WorkshopPlanHold.objects.filter(
            workspace=draft.workspace,
            status=WorkshopPlanHold.Status.ACTIVE,
            expires_at__lte=now,
        ).update(status=WorkshopPlanHold.Status.RELEASED, updated_by=request.user)
        # Count after the sweep above, so expired reservations do not count
        # against anybody. A reservation removes a trainer's time for seventy-two
        # hours, so how many one person may hold at once is a direct limit on
        # everybody else's ability to book -- and nothing bounded it before.
        held = (
            WorkshopPlanHold.objects.filter(
                workspace=draft.workspace,
                draft__owner=request.user,
                status=WorkshopPlanHold.Status.ACTIVE,
                expires_at__gt=now,
            )
            .exclude(draft=draft)
            .count()
        )
        if held >= settings.CAPACITY_MAX_ACTIVE_HOLDS_PER_USER:
            return Response(
                {
                    "error": (
                        "You are already holding as much trainer time as this workspace allows. "
                        "Release a reservation before taking another."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        conflict = _blocks_conflict(
            workspace=draft.workspace,
            trainer=trainer,
            blocked_start=blocked_start,
            blocked_end=blocked_end,
            now=now,
            excluding_draft=draft,
        )
        if conflict:
            return Response(
                {"error": "This trainer is no longer available for the complete block."},
                status=status.HTTP_409_CONFLICT,
            )

        WorkshopPlanHold.objects.filter(draft=draft, status=WorkshopPlanHold.Status.ACTIVE).update(
            status=WorkshopPlanHold.Status.RELEASED,
            updated_by=request.user,
        )
        hold = WorkshopPlanHold.objects.create(
            draft=draft,
            workspace=draft.workspace,
            trainer=trainer.user,
            workshop_starts_at=workshop_start,
            workshop_ends_at=workshop_end,
            blocked_starts_at=blocked_start,
            blocked_ends_at=blocked_end,
            expires_at=now + timedelta(hours=72),
            created_by=request.user,
            updated_by=request.user,
        )
        draft.revision += 1
        draft.updated_by = request.user
        draft.save(update_fields=["revision", "updated_by", "updated_at"])
        _audit(
            request,
            workspace_id=draft.workspace_id,
            trainer_id=trainer_id,
            action=CapacityAuditEvent.Action.PLAN_HOLD_CREATED,
            metadata={"draft_id": str(draft.id), "hold_id": str(hold.id)},
        )
        return Response({"hold": _hold_payload(hold), "revision": draft.revision}, status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @transaction.atomic
    def delete(self, request, slug, draft_id):
        if response := _disabled():
            return response
        draft = self._draft(request, slug, draft_id)
        hold = draft.holds.filter(status=WorkshopPlanHold.Status.ACTIVE).first()
        if hold is None:
            return Response(status=204)
        hold.status = WorkshopPlanHold.Status.RELEASED
        hold.updated_by = request.user
        hold.save(update_fields=["status", "updated_by", "updated_at"])
        draft.revision += 1
        draft.updated_by = request.user
        draft.save(update_fields=["revision", "updated_by", "updated_at"])
        _audit(
            request,
            workspace_id=draft.workspace_id,
            trainer_id=hold.trainer_id,
            action=CapacityAuditEvent.Action.PLAN_HOLD_RELEASED,
            metadata={"draft_id": str(draft.id), "hold_id": str(hold.id)},
        )
        return Response({"revision": draft.revision})


class WorkshopSearchEndpoint(BaseAPIView):
    """
    Workshop work items the requester can actually plan, for the planner's picker.

    Deliberately server-side rather than filtering the generic entity search in
    the browser. "Only a Workshop work item can be planned" is a rule the
    scheduling endpoint enforces, and a picker that offered anything else would
    be inviting a refusal; project visibility is the same story. Doing both here
    keeps one answer to both questions.
    """

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        query = (request.GET.get("query") or "").strip()
        visible_projects = ProjectMember.objects.filter(member=request.user, is_active=True).values_list(
            "project_id", flat=True
        )
        issues = Issue.objects.filter(
            workspace__slug=slug,
            project_id__in=visible_projects,
            type__system_key=IssueType.SystemKey.WORKSHOP,
        ).select_related("project")
        if query:
            issues = issues.filter(name__icontains=query)
        return Response({"results": [_issue_payload(issue) for issue in issues.order_by("-created_at")[:20]]})


class WorkshopPlanScheduleEndpoint(BaseAPIView):
    """
    Spend a hold: turn it into a real session on the work item it was for.

    This is the step the planner never had. A hold named a trainer and a block
    that existed nowhere else, so the only way to act on it was to retype both
    into the work item by hand -- after which the hold stayed put, quietly
    blocking that trainer until it expired, on top of the session just created.

    Everything happens in one transaction, and the conflict check that guarded
    the hold is run again here rather than trusted: up to seventy-two hours pass
    between taking a hold and spending it, and the workspace does not stand
    still. A refusal leaves the hold intact, so the coordinator can pick another
    slot rather than losing the one they had.
    """

    # Same reasoning as the hold endpoint: its preflight reads Google first.
    authentication_classes = [CsrfEnforcedSessionAuthentication]
    throttle_classes = [CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    @booking_preflight(scheduling=True)
    @transaction.atomic
    def post(self, request, slug, draft_id):
        if response := _disabled():
            return response
        draft = get_object_or_404(
            # `of=("self",)` because `issue` is nullable: select_related makes it a
            # LEFT JOIN, and PostgreSQL refuses FOR UPDATE on the nullable side of
            # one. The draft row is the only thing that needs locking anyway.
            WorkshopPlanDraft.objects.select_for_update(of=("self",)).select_related("issue__project", "issue__type"),
            workspace__slug=slug,
            owner=request.user,
            pk=draft_id,
        )
        raw_key = request.data.get("idempotency_key")
        try:
            operation_key = UUID(str(raw_key)) if raw_key else None
        except ValueError:
            return Response({"error": "idempotency_key must be a UUID."}, status=400)
        fingerprint = hashlib.sha256(json.dumps(dict(request.data), sort_keys=True).encode()).hexdigest()
        if operation_key:
            operation = draft.booking_operations.filter(key=operation_key).first()
            if operation:
                if operation.request_fingerprint != fingerprint:
                    return Response({"error": "This operation key belongs to another request."}, status=409)
                if not ProjectMember.objects.filter(
                    project_id=operation.result["issue"]["project_id"], member=request.user, is_active=True
                ).exists():
                    return Response({"error": "No such Workshop work item in this workspace."}, status=404)
                return Response(operation.result, status=200)
        try:
            revision = int(request.data.get("revision"))
        except (TypeError, ValueError):
            return Response({"error": "revision is required."}, status=400)
        if revision != draft.revision:
            return Response(
                {"error": "Draft changed after you opened it.", "revision": draft.revision},
                status=status.HTTP_409_CONFLICT,
            )

        issue = draft.issue
        if issue is None:
            return Response({"error": "Attach a Workshop work item to this plan before scheduling it."}, status=400)
        # Re-checked rather than trusted from when the draft was saved: a work
        # item can change type, and the requester can lose the project.
        if not issue.type_id or issue.type.system_key != IssueType.SystemKey.WORKSHOP:
            return Response({"error": "Only Workshop work items can be scheduled."}, status=400)
        if not ProjectMember.objects.filter(
            project_id=issue.project_id, member=request.user, role__gte=ROLE.MEMBER.value, is_active=True
        ).exists():
            return Response({"error": "No such Workshop work item in this workspace."}, status=404)

        now = timezone.now()
        hold = draft.holds.filter(status=WorkshopPlanHold.Status.ACTIVE, expires_at__gt=now).first()
        direct = "trainer_id" in request.data or "workshop_starts_at" in request.data
        if hold is None and direct:
            if operation_key is None:
                return Response({"error": "idempotency_key is required for direct scheduling."}, status=400)
            snapshot = request.capacity_booking_snapshot
            hold = WorkshopPlanHold(
                draft=draft,
                workspace=draft.workspace,
                trainer_id=snapshot["trainer"],
                workshop_starts_at=snapshot["start"],
                workshop_ends_at=snapshot["end"],
                blocked_starts_at=snapshot["blocked_start"],
                blocked_ends_at=snapshot["blocked_end"],
                expires_at=now + timedelta(hours=72),
                created_by=request.user,
                updated_by=request.user,
            )
        if hold is None:
            return Response({"error": "Hold a slot or choose a candidate before scheduling it."}, status=400)

        trainer = (
            TrainerProfile.objects.select_for_update()
            .select_related("user")
            .filter(workspace=draft.workspace, user_id=hold.trainer_id, status=TrainerProfile.Status.ACTIVE)
            .first()
        )
        if trainer is None:
            return Response({"error": "The held trainer is no longer active in this workspace."}, status=409)

        if response := snapshot_error(request, draft, trainer):
            return response
        if _blocks_conflict(
            workspace=draft.workspace,
            trainer=trainer,
            blocked_start=hold.blocked_starts_at,
            blocked_end=hold.blocked_ends_at,
            now=now,
            excluding_hold=hold,
        ):
            return Response(
                {"error": "That block is no longer free. The hold is untouched; pick another slot."},
                status=status.HTTP_409_CONFLICT,
            )

        # Serialize all appenders on the parent issue, including first-session creation.
        issue = Issue.objects.select_for_update().get(pk=issue.pk)
        schedule, created = WorkshopSchedule.objects.get_or_create(
            issue=issue,
            defaults={
                "starts_at": hold.workshop_starts_at,
                "ends_at": hold.workshop_ends_at,
                "preparation_minutes": draft.preparation_minutes,
                "travel_before_minutes": draft.travel_before_minutes,
                "travel_after_minutes": draft.travel_after_minutes,
            },
        )
        # Appended rather than replacing: a workshop runs over several sessions,
        # and each is planned on its own. Appending also leaves the schedule's
        # own mirror of position 0 alone, which is what `_payload` reads when a
        # schedule predates multi-session support.
        existing = list(schedule.sessions.values_list("position", flat=True))
        if len(existing) >= 50:
            return Response({"error": "A Workshop may not have more than 50 sessions."}, status=400)
        if hold.pk is None or hold._state.adding:
            hold.save()
        session = WorkshopSession.objects.create(
            schedule=schedule,
            source_plan=draft,
            source_hold=hold,
            position=max(existing) + 1 if existing else 0,
            starts_at=hold.workshop_starts_at,
            ends_at=hold.workshop_ends_at,
            preparation_minutes=draft.preparation_minutes,
            travel_before_minutes=draft.travel_before_minutes,
            travel_after_minutes=draft.travel_after_minutes,
        )
        session.trainers.add(trainer.user_id)

        # The work item's own rule is that every session trainer is an assignee,
        # so scheduling makes that true rather than refusing over it -- and says
        # so in the work item's history, where an assignment that appeared from
        # nowhere would otherwise be a small mystery.
        assignees = list(issue.issue_assignee.values_list("assignee_id", flat=True))
        if trainer.user_id not in assignees:
            IssueAssignee.objects.create(
                issue=issue,
                assignee_id=trainer.user_id,
                project_id=issue.project_id,
                workspace_id=issue.workspace_id,
                created_by=request.user,
                updated_by=request.user,
            )
            transaction.on_commit(
                lambda: issue_activity.delay(
                    type="issue.activity.updated",
                    requested_data=json.dumps(
                        {"assignee_ids": [str(value) for value in [*assignees, trainer.user_id]]}, cls=DjangoJSONEncoder
                    ),
                    current_instance=json.dumps(
                        {"assignee_ids": [str(value) for value in assignees]}, cls=DjangoJSONEncoder
                    ),
                    issue_id=str(issue.id),
                    actor_id=str(request.user.id),
                    project_id=str(issue.project_id),
                    epoch=int(now.timestamp()),
                    notification=True,
                    origin=base_host(request=request, is_app=True),
                )
            )

        # The workshop now has a date, so any checklist subtask that was created
        # before it had one can finally be dated. Only the undated ones move.
        backfill_target_dates(issue)

        # Record what the shared calendar ought to say, inside the booking's own
        # transaction. A worker sends it afterwards, so a slow or unreachable
        # Google cannot make a booking fail -- and a transaction that rolls back
        # takes the intent with it rather than leaving an invitation for a
        # session that never existed.
        enqueue(reconcile_session(session, actor=request.user))

        hold.status = WorkshopPlanHold.Status.SCHEDULED
        hold.updated_by = request.user
        hold.save(update_fields=["status", "updated_by", "updated_at"])
        draft.revision += 1
        draft.updated_by = request.user
        draft.save(update_fields=["revision", "updated_by", "updated_at"])
        _audit(
            request,
            workspace_id=draft.workspace_id,
            trainer_id=trainer.user_id,
            issue_id=issue.id,
            action=CapacityAuditEvent.Action.PLAN_SCHEDULED,
            metadata={
                "draft_id": str(draft.id),
                "hold_id": str(hold.id),
                "session_id": str(session.id),
                "schedule_created": created,
            },
        )
        result = {
            "revision": draft.revision,
            "issue": _issue_payload(issue),
            "session": {
                "id": str(session.id),
                "starts_at": session.starts_at.isoformat(),
                "ends_at": session.ends_at.isoformat(),
                "trainer_ids": [str(trainer.user_id)],
            },
        }
        if operation_key:
            WorkshopBookingOperation.objects.create(
                draft=draft,
                key=operation_key,
                request_fingerprint=fingerprint,
                result=result,
                created_by=request.user,
                updated_by=request.user,
            )
        return Response(result, status=status.HTTP_201_CREATED)


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
        assignees = set(issue.issue_assignee.values_list("assignee_id", flat=True))
        if not assignees:
            return Response({"error": "A Workshop requires at least one trainer."}, status=400)
        # Whom a session gets when it does not name anybody: the work item's
        # trainer property, which is where the coordinator says who delivers this
        # training. A workshop from before the property falls back to its
        # assignees, which is what the property will hold once anybody edits it.
        default_trainer_ids = [value for value in delivering_trainer_ids(issue) if value in assignees] or list(
            assignees
        )
        active_trainers = set(
            TrainerProfile.objects.filter(
                workspace=issue.workspace, user_id__in=assignees, status="active"
            ).values_list("user_id", flat=True)
        )
        if assignees - active_trainers:
            return Response({"error": "Every Workshop assignee must be an active trainer."}, status=400)

        raw_sessions = request.data.get("sessions")
        if raw_sessions is None:
            raw_sessions = [request.data]
        if not isinstance(raw_sessions, list) or not 1 <= len(raw_sessions) <= 50:
            return Response({"error": "A Workshop requires between 1 and 50 sessions."}, status=400)

        parsed_sessions = []
        for position, item in enumerate(raw_sessions):
            if not isinstance(item, dict):
                return Response({"error": f"Session {position + 1} must be an object."}, status=400)
            starts_at = parse_datetime(item.get("starts_at", ""))
            ends_at = parse_datetime(item.get("ends_at", ""))
            if (
                not starts_at
                or not ends_at
                or timezone.is_naive(starts_at)
                or timezone.is_naive(ends_at)
                or starts_at >= ends_at
            ):
                return Response({"error": f"Session {position + 1} requires a valid timezone-aware range."}, status=400)
            if ends_at - starts_at > timedelta(days=7):
                return Response({"error": f"Session {position + 1} may not exceed seven days."}, status=400)
            values = {}
            for field in ("preparation_minutes", "travel_before_minutes", "travel_after_minutes"):
                try:
                    value = int(item.get(field, 0))
                except (TypeError, ValueError):
                    return Response({"error": f"Session {position + 1}: {field} must be an integer."}, status=400)
                if not 0 <= value <= 1440:
                    return Response(
                        {"error": f"Session {position + 1}: {field} must be between 0 and 1440."}, status=400
                    )
                values[field] = value
            raw_trainer_ids = item.get("trainer_ids", default_trainer_ids)
            if not isinstance(raw_trainer_ids, list) or not raw_trainer_ids:
                return Response({"error": f"Session {position + 1} requires at least one trainer."}, status=400)
            try:
                trainer_ids = {UUID(str(value)) for value in raw_trainer_ids}
            except (TypeError, ValueError, AttributeError):
                return Response({"error": f"Session {position + 1} contains an invalid trainer ID."}, status=400)
            if not trainer_ids.issubset(active_trainers):
                return Response(
                    {"error": f"Every trainer in session {position + 1} must be an active Workshop assignee."},
                    status=400,
                )
            try:
                session_id = str(UUID(str(item["id"]))) if item.get("id") else None
            except (ValueError, TypeError):
                return Response({"error": "A session ID must be a UUID."}, status=400)
            parsed_sessions.append(
                {"id": session_id, "starts_at": starts_at, "ends_at": ends_at, "trainer_ids": trainer_ids, **values}
            )

        # Overlap is checked here too, not only in the planner.
        #
        # Three paths create sessions -- the planner, this editor and the
        # calendar import -- and until now only the planner asked whether the
        # trainer was already taken. A coordinator could place a session straight
        # on top of another coordinator's hold or workshop, and the resulting row
        # then blocked everybody else through the very check it had skipped.
        #
        # Deliberately the database-only question the planner already asks, not a
        # Google read: this endpoint has never talked to Google, and making it do
        # so would give editing a workshop a new way to fail that has nothing to
        # do with the edit. Google availability stays the planner's concern, at
        # the point where time is actually being taken.
        conflict = _schedule_conflict(issue=issue, parsed_sessions=parsed_sessions, now=timezone.now())
        if conflict:
            return Response({"error": conflict}, status=409)

        # Use the planner's lock order: trainer profiles, then the parent issue.
        list(
            TrainerProfile.objects.select_for_update()
            .filter(workspace=issue.workspace, user_id__in=active_trainers)
            .order_by("id")
        )
        Issue.objects.select_for_update().get(pk=issue.pk)
        existing = {str(session.id): session for session in WorkshopSession.objects.filter(schedule__issue=issue)}
        retained = [item["id"] for item in parsed_sessions if item["id"]]
        if len(retained) != len(set(retained)) or any(session_id not in existing for session_id in retained):
            return Response({"error": "Session IDs must be unique and belong to this Workshop."}, status=400)
        first = parsed_sessions[0]
        schedule, _ = WorkshopSchedule.objects.update_or_create(
            issue=issue,
            defaults={
                "starts_at": first["starts_at"],
                "ends_at": first["ends_at"],
                "preparation_minutes": first["preparation_minutes"],
                "travel_before_minutes": first["travel_before_minutes"],
                "travel_after_minutes": first["travel_after_minutes"],
            },
        )
        # Collect before deleting: afterwards there is nothing left to
        # enumerate, and these are exactly the sessions whose invitations still
        # have to be withdrawn from the calendar.
        departing = list(schedule.sessions.exclude(id__in=retained).values_list("id", flat=True))
        schedule.sessions.exclude(id__in=retained).delete(soft=False)
        # Move retained positions aside before reordering under the unique constraint.
        schedule.sessions.update(position=F("position") + 1000)
        touched = []
        for position, values in enumerate(parsed_sessions):
            trainer_ids = values.pop("trainer_ids")
            session_id = values.pop("id")
            if session_id:
                session = existing[session_id]
                for field, value in values.items():
                    setattr(session, field, value)
                session.position = position
                session.save(update_fields=[*values, "position", "updated_at"])
            else:
                session = WorkshopSession.objects.create(schedule=schedule, position=position, **values)
            session.trainers.set(trainer_ids)
            touched.extend(reconcile_session(session, actor=request.user))
        backfill_target_dates(issue)
        touched.extend(mark_sessions_absent(departing, actor=request.user))
        enqueue(touched)
        _audit(
            request,
            workspace_id=issue.workspace_id,
            issue_id=issue.id,
            action=CapacityAuditEvent.Action.WORKSHOP_UPDATED,
            metadata={"session_count": len(parsed_sessions)},
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
        # Same order as above: name the sessions while they still exist, because
        # the invitations they sent outlive them and have to be withdrawn.
        departing = list(WorkshopSession.objects.filter(schedule__issue=issue).values_list("id", flat=True))
        touched = mark_sessions_absent(departing, actor=request.user)
        WorkshopSchedule.objects.filter(issue=issue).delete(soft=False)
        enqueue(touched)
        _audit(
            request,
            workspace_id=issue.workspace_id,
            issue_id=issue.id,
            action=CapacityAuditEvent.Action.WORKSHOP_REMOVED,
        )
        return Response(status=204)

    @staticmethod
    def _calendar_sync(session_ids):
        """What the shared calendar currently says about each session.

        Returned per session and per trainer rather than as one verdict: a
        session delivered by two people can have one invitation sent and the
        other blocked on a trainer who never connected Google, and collapsing
        that into "partly synced" tells nobody which of them to chase.

        Absent rows are omitted deliberately. A withdrawal in progress is not
        something the person editing the schedule can act on, and listing
        trainers who are no longer on a session would be confusing.
        """
        if not writeback_enabled() or not session_ids:
            return {}
        rows = WorkshopSessionCalendarEvent.objects.filter(
            source_session_id__in=session_ids, intent=WorkshopSessionCalendarEvent.Intent.PRESENT
        ).values(
            "source_session_id",
            "trainer_id",
            "state",
            "last_error_code",
            "synced_at",
            "revision",
            "synced_revision",
        )
        by_session = {}
        for row in rows:
            by_session.setdefault(str(row["source_session_id"]), []).append(
                {
                    "trainer_id": str(row["trainer_id"]),
                    # A row whose desired state has moved on is still working,
                    # whatever it last recorded -- reporting `synced` there would
                    # promise a calendar entry that does not exist yet.
                    "state": (
                        row["state"]
                        if row["synced_revision"] == row["revision"]
                        else WorkshopSessionCalendarEvent.State.PENDING
                    ),
                    "last_error_code": row["last_error_code"],
                    "synced_at": row["synced_at"].isoformat() if row["synced_at"] else None,
                }
            )
        return by_session

    @staticmethod
    def _payload(schedule):
        sessions = list(schedule.sessions.prefetch_related("trainers").all())
        sync = WorkshopScheduleEndpoint._calendar_sync([session.id for session in sessions])
        if not sessions:
            trainer_ids = [str(value) for value in schedule.issue.issue_assignee.values_list("assignee_id", flat=True)]
            session_payloads = [
                {
                    "id": None,
                    "starts_at": schedule.starts_at.isoformat(),
                    "ends_at": schedule.ends_at.isoformat(),
                    "preparation_minutes": schedule.preparation_minutes,
                    "travel_before_minutes": schedule.travel_before_minutes,
                    "travel_after_minutes": schedule.travel_after_minutes,
                    "trainer_ids": trainer_ids,
                    "calendar_sync": [],
                }
            ]
        else:
            session_payloads = [
                {
                    "id": str(session.id),
                    "starts_at": session.starts_at.isoformat(),
                    "ends_at": session.ends_at.isoformat(),
                    "preparation_minutes": session.preparation_minutes,
                    "travel_before_minutes": session.travel_before_minutes,
                    "travel_after_minutes": session.travel_after_minutes,
                    "trainer_ids": [str(trainer.id) for trainer in session.trainers.all()],
                    "calendar_sync": sync.get(str(session.id), []),
                }
                for session in sessions
            ]
        return {
            "issue_id": str(schedule.issue_id),
            "starts_at": schedule.starts_at.isoformat(),
            "ends_at": schedule.ends_at.isoformat(),
            "preparation_minutes": schedule.preparation_minutes,
            "travel_before_minutes": schedule.travel_before_minutes,
            "travel_after_minutes": schedule.travel_after_minutes,
            "sessions": session_payloads,
        }
