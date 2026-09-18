# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""How much training a team actually ran, over any period.

The question the weekly ledger cannot answer, because it asks Google live and
Google will not serve a month for a roster in one request. This reads the
materialized table instead and makes no outbound call at all -- which is the
entire reason that table exists.

That trade is honest only if the answer says how fresh it is. A trainer whose
consent lapsed has no occurrences, and rendering them as somebody who ran no
training would be a quiet lie in a document people plan staffing from. So the
response carries a freshness vocabulary and excludes such trainers from the
totals rather than counting them as zero.
"""

import csv
import io
from datetime import timedelta
from uuid import UUID

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.db.models import Workspace
from plane.ext.capacity.throttles import CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle
from plane.ext.capacity.training_workload import empty_counts, external_counts, linked_sessions
from plane.ext.capacity.workload import session_workload
from plane.ext.models import (
    TrainerProfile,
    TrainerTrainingSyncState,
    TrainingCalendarSyncState,
    TrainingEventOccurrence,
)
from plane.ext.services.training_import import parse_range
from plane.ext.views.capacity import _disabled
from plane.utils.csv_utils import sanitize_csv_row
from plane.utils.permissions import ROLE, allow_permission

# Deliberately not the ledger's fourteen days. That cap exists because every day
# of it costs a Google request; this endpoint makes none, so the only reason to
# bound the range at all is to keep one report from scanning a decade.
MAX_RANGE = timedelta(days=400)

# Older than this and the report says so rather than implying the numbers are
# current. Two hours is several sweep cycles: past it, something is wrong.
STALE_AFTER = timedelta(hours=2)

CSV_COLUMNS = [
    "Trainer",
    "Data status",
    "Workshops",
    "Sessions",
    "Delivery hours",
    "Preparation and travel hours",
    "External confirmed",
    "External confirmed hours",
    "External pending",
    "External pending hours",
]


def _hours(minutes):
    return round(minutes / 60, 2)


def _sync_status(profile, now):
    """Whether this trainer's numbers can be trusted, and why not when they cannot.

    Consent alone is not enough to answer. A trainer can have consented
    perfectly and still have no current data, because the sweep of the calendar
    they appear on has been failing -- a calendar stuffed past the event ceiling
    does exactly that, and the backoff then retries into the same wall. Reading
    only `consent_state` reported those trainers as fully counted, which is the
    one thing this report must never do: it is read by somebody planning who can
    take the next workshop.
    """
    state = getattr(profile, "training_sync_state", None)
    if state is None or state.last_materialized_at is None:
        return "never_synced"
    if state.consent_state != TrainerTrainingSyncState.ConsentState.OK:
        return state.consent_state
    if now - state.last_materialized_at > STALE_AFTER:
        return "stale"
    return "ok"


def _coverage(workspace_id, start, end):
    states = list(
        TrainingCalendarSyncState.objects.filter(workspace_id=workspace_id).select_related("rule")
    )
    now = timezone.now()
    calendars = []
    successes = []
    for state in states:
        if state.last_success_at:
            successes.append(state.last_success_at)
        if state.last_error_code:
            status = "unavailable"
        elif state.last_success_at and now - state.last_success_at > STALE_AFTER:
            status = "stale"
        elif state.last_success_at is None:
            status = "unavailable"
        else:
            status = "ok"
        calendars.append(
            {
                "rule_label": state.rule.label if state.rule_id else "",
                "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None,
                "last_full_scan_at": state.last_full_scan_at.isoformat() if state.last_full_scan_at else None,
                "status": status,
            }
        )
    window_start = min((state.window_starts_at for state in states), default=None)
    window_end = max((state.window_ends_at for state in states), default=None)
    covered = bool(states) and window_start <= start and window_end >= end
    return {
        "window_starts_at": window_start.isoformat() if window_start else None,
        "window_ends_at": window_end.isoformat() if window_end else None,
        "requested_range_covered": covered,
        "calendars": calendars,
    }, (min(successes) if successes else None)


class TrainingReportEndpoint(BaseAPIView):
    """Delivered and external training per trainer, over any period."""

    throttle_classes = [CalendarCapacityUserThrottle, CalendarCapacityWorkspaceThrottle]

    @allow_permission([ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def get(self, request, slug):
        if response := _disabled():
            return response
        start, end, error = parse_range(request.GET.get("from"), request.GET.get("to"))
        if error:
            return Response({"error": error}, status=400)
        if end - start > MAX_RANGE:
            return Response({"error": "Report range may not exceed 400 days."}, status=400)

        raw_ids = [value for value in request.GET.get("trainer_ids", "").split(",") if value]
        try:
            trainer_ids = [str(UUID(value)) for value in raw_ids]
        except ValueError:
            return Response({"error": "trainer_ids must be UUIDs."}, status=400)

        workspace = get_object_or_404(Workspace, slug=slug)
        profiles = (
            TrainerProfile.objects.filter(workspace=workspace, status=TrainerProfile.Status.ACTIVE)
            .select_related("user", "training_sync_state")
            .order_by("user__display_name", "id")
        )
        if trainer_ids:
            profiles = profiles.filter(user_id__in=trainer_ids)
        profiles = list(profiles)

        rows = self._rows(workspace, profiles, start, end, timezone.now())
        coverage, data_as_of = _coverage(workspace.id, start, end)

        # Deliberately not `format`: DRF reserves that query parameter for
        # renderer negotiation, and an unknown value there makes it answer 404
        # before this view ever runs.
        if request.GET.get("export") == "csv":
            return self._csv(rows, slug, start, end)

        return Response(
            {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "data_as_of": data_as_of.isoformat() if data_as_of else None,
                "coverage": coverage,
                "trainers": rows,
            }
        )

    @staticmethod
    def _rows(workspace, profiles, start, end, now):
        user_ids = [profile.user_id for profile in profiles]
        delivered = session_workload(workspace.id, user_ids, start, end)
        occurrences = TrainingEventOccurrence.objects.filter(
            workspace=workspace,
            trainer_id__in=user_ids,
            state=TrainingEventOccurrence.State.ACTIVE,
            starts_at__lt=end,
            ends_at__gt=start,
        ).values_list("trainer_id", "event_key", "starts_at", "ends_at", "status")

        by_trainer = {user_id: [] for user_id in user_ids}
        for trainer_id, key, starts_at, ends_at, status in occurrences:
            by_trainer[trainer_id].append((key, starts_at, ends_at, status))

        rows = []
        for profile in profiles:
            sync_status = _sync_status(profile, now)
            mine = by_trainer.get(profile.user_id, [])
            if sync_status == "ok":
                linked = linked_sessions(
                    workspace.id, profile.user_id, [item[0] for item in mine], start, end
                )
                external = external_counts(mine, linked=linked, start=start, end=end)
            else:
                # No usable data for this trainer. Reporting zeroes would read as
                # "ran nothing"; the caller is told to leave them out of totals.
                external = empty_counts()
            rows.append(
                {
                    "trainer_id": str(profile.user_id),
                    "display_name": profile.user.display_name,
                    "sync_status": sync_status,
                    "counts_towards_totals": sync_status == "ok",
                    **delivered[profile.user_id],
                    "external_confirmed_sessions": external["confirmed_sessions"],
                    "external_confirmed_minutes": external["confirmed_minutes"],
                    "external_pending_sessions": external["pending_sessions"],
                    "external_pending_minutes": external["pending_minutes"],
                }
            )
        return rows

    @staticmethod
    def _csv(rows, slug, start, end):
        buffer = io.StringIO()
        writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
        writer.writerow(sanitize_csv_row(CSV_COLUMNS))
        for row in rows:
            writer.writerow(
                sanitize_csv_row(
                    [
                        row["display_name"],
                        row["sync_status"],
                        row["workshop_count"],
                        row["session_count"],
                        _hours(row["delivery_minutes"]),
                        _hours(row["buffer_minutes"]),
                        row["external_confirmed_sessions"],
                        _hours(row["external_confirmed_minutes"]),
                        row["external_pending_sessions"],
                        _hours(row["external_pending_minutes"]),
                    ]
                )
            )
        response = HttpResponse(buffer.getvalue(), content_type="text/csv")
        name = f"training-{slug}-{start:%Y%m%d}-{end:%Y%m%d}.csv"
        response["Content-Disposition"] = f"attachment; filename={name}"
        return response
