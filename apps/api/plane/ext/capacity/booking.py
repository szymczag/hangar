# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import timedelta
from functools import wraps
from uuid import UUID

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response

from plane.ext.capacity.calculation import _google_busy, _intersections, _subtract, _working_intervals
from plane.ext.models import TrainerProfile, WorkshopPlanDraft


def selection_revision(trainer):
    selection = getattr(trainer, "calendar_selection", None)
    return (
        (selection.pk, selection.revision, selection.credential_id, selection.credential.status) if selection else None
    )


def booking_preflight(*, scheduling=False):
    """Read Google before taking SQL locks; revalidate the snapshot under locks."""

    def decorate(method):
        @wraps(method)
        def wrapped(self, request, slug, draft_id):
            from plane.ext.views.capacity import _disabled

            if response := _disabled():
                return response
            draft = get_object_or_404(WorkshopPlanDraft, workspace__slug=slug, owner=request.user, pk=draft_id)
            # A successful retry must not fail because the original time is now past.
            if scheduling and request.data.get("idempotency_key"):
                try:
                    key = UUID(str(request.data["idempotency_key"]))
                except ValueError:
                    return Response({"error": "idempotency_key must be a UUID."}, status=400)
                operation = draft.booking_operations.filter(key=key).first()
                if operation:
                    return method(self, request, slug, draft_id)
            hold = draft.holds.filter(status="active", expires_at__gt=timezone.now()).first() if scheduling else None
            direct = "trainer_id" in request.data or "workshop_starts_at" in request.data
            if scheduling and hold and direct:
                return Response({"error": "Choose either the active reservation or a new candidate."}, status=400)
            try:
                trainer_id = hold.trainer_id if hold else UUID(str(request.data.get("trainer_id")))
                start = hold.workshop_starts_at if hold else parse_datetime(request.data.get("workshop_starts_at", ""))
                revision = int(request.data.get("revision"))
            except (TypeError, ValueError, AttributeError):
                return Response({"error": "revision, trainer_id and workshop_starts_at are required."}, status=400)
            if revision != draft.revision:
                return Response({"error": "Draft changed after you opened it.", "revision": draft.revision}, status=409)
            if not start or timezone.is_naive(start):
                return Response({"error": "A timezone-aware workshop_starts_at is required."}, status=400)
            trainer = get_object_or_404(
                TrainerProfile.objects.select_related("user").prefetch_related("calendar_selection__credential"),
                workspace=draft.workspace,
                user_id=trainer_id,
                status="active",
            )
            end = start + timedelta(minutes=draft.duration_minutes)
            blocked_start = start - timedelta(minutes=draft.preparation_minutes + draft.travel_before_minutes)
            blocked_end = end + timedelta(minutes=draft.travel_after_minutes)
            if blocked_start <= timezone.now():
                return Response({"error": "The trainer block has already started."}, status=400)
            if str(trainer_id) not in draft.trainer_ids:
                return Response({"error": "The trainer is not eligible for this plan."}, status=400)
            if _subtract([(blocked_start, blocked_end)], _working_intervals(trainer, blocked_start, blocked_end)):
                return Response({"error": "The complete block must fit inside booking hours."}, status=409)
            busy, connection, freshness = _google_busy(trainer, blocked_start, blocked_end, force=True)
            if selection_revision(trainer) and freshness != "fresh":
                return Response(
                    {
                        "error": "Google availability could not be verified. Retry before booking.",
                        "code": "availability_unverified",
                    },
                    status=503,
                )
            if _intersections([(blocked_start, blocked_end)], busy):
                return Response({"error": "The trainer is busy in Google during this block."}, status=409)
            request.capacity_booking_snapshot = {
                "trainer": str(trainer_id),
                "draft_revision": draft.revision,
                "schedule_revision": trainer.schedule_revision,
                "timezone": trainer.timezone,
                "selection_revision": selection_revision(trainer),
                "start": start,
                "end": end,
                "blocked_start": blocked_start,
                "blocked_end": blocked_end,
            }
            return method(self, request, slug, draft_id)

        return wrapped

    return decorate


def snapshot_error(request, draft, trainer):
    snapshot = getattr(request, "capacity_booking_snapshot", None)
    if not snapshot or (
        snapshot["draft_revision"] != draft.revision
        or snapshot["trainer"] != str(trainer.user_id)
        or snapshot["schedule_revision"] != trainer.schedule_revision
        or snapshot["timezone"] != trainer.timezone
        or snapshot["selection_revision"] != selection_revision(trainer)
    ):
        return Response({"error": "Availability changed while checking. Refresh and try again."}, status=409)
    if snapshot["blocked_start"] <= timezone.now():
        return Response({"error": "The trainer block has already started."}, status=409)
    if _subtract(
        [(snapshot["blocked_start"], snapshot["blocked_end"])],
        _working_intervals(trainer, snapshot["blocked_start"], snapshot["blocked_end"]),
    ):
        return Response({"error": "Booking hours changed. Refresh and try again."}, status=409)
    return None
