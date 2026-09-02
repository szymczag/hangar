# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone as dt_timezone
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from django.core.exceptions import ObjectDoesNotExist
from django.core.cache import cache
from django.db import close_old_connections

from plane.db.models import ProjectMember
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.capacity.cache import BUSY_CACHE_TTL_SECONDS, register_busy_cache_key
from plane.ext.capacity.google import GoogleCalendarClient, GoogleCalendarError
from plane.ext.models import TrainerProfile, WorkshopSchedule
from plane.license.utils.instance_value import get_configuration_value

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GOOGLE_CACHE_WINDOW_MINUTES = 15


def _merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _intersections(left, right):
    result = []
    for left_start, left_end in left:
        for right_start, right_end in right:
            start, end = max(left_start, right_start), min(left_end, right_end)
            if start < end:
                result.append((start, end))
    return _merge(result)


def _minutes(intervals):
    return int(sum((end - start).total_seconds() for start, end in _merge(intervals)) // 60)


def _subtract(intervals, blockers):
    remaining = []
    merged_blockers = _merge(blockers)
    for interval_start, interval_end in _merge(intervals):
        cursor = interval_start
        for blocker_start, blocker_end in merged_blockers:
            if blocker_end <= cursor or blocker_start >= interval_end:
                continue
            if cursor < blocker_start:
                remaining.append((cursor, min(blocker_start, interval_end)))
            cursor = max(cursor, blocker_end)
            if cursor >= interval_end:
                break
        if cursor < interval_end:
            remaining.append((cursor, interval_end))
    return remaining


def _working_intervals(trainer, start, end):
    zone = ZoneInfo(trainer.timezone)
    exceptions = {item.local_date: item for item in trainer.schedule_exceptions.all()}
    local_date = start.astimezone(zone).date()
    last_date = (end - timedelta(microseconds=1)).astimezone(zone).date()
    result = []
    while local_date <= last_date:
        exception = exceptions.get(local_date)
        if exception and exception.mode == exception.Mode.UNAVAILABLE:
            values = []
        elif exception and exception.mode == exception.Mode.OVERRIDE:
            values = exception.intervals
        else:
            values = trainer.weekly_schedule.get(DAY_KEYS[local_date.weekday()], [])
        for value in values:
            local_start = datetime.combine(local_date, time.fromisoformat(value["start"]), tzinfo=zone)
            local_end = datetime.combine(local_date, time.fromisoformat(value["end"]), tzinfo=zone)
            interval = (
                max(start, local_start.astimezone(dt_timezone.utc)),
                min(end, local_end.astimezone(dt_timezone.utc)),
            )
            if interval[0] < interval[1]:
                result.append(interval)
        local_date += timedelta(days=1)
    return _merge(result)


def _google_client():
    client_id, client_secret = get_configuration_value(
        [
            {"key": "GOOGLE_CLIENT_ID", "default": ""},
            {"key": "GOOGLE_CLIENT_SECRET", "default": ""},
        ]
    )
    if not client_id or not client_secret:
        raise GoogleCalendarError("not_configured")
    return GoogleCalendarClient(client_id=client_id, client_secret=client_secret)


def _google_busy(trainer, start, end):
    try:
        selection = trainer.calendar_selection
    except ObjectDoesNotExist:
        return [], "not_connected"
    credential = selection.credential
    if credential.status != credential.Status.CONNECTED:
        return [], credential.status
    normalized_start = start.replace(
        minute=(start.minute // GOOGLE_CACHE_WINDOW_MINUTES) * GOOGLE_CACHE_WINDOW_MINUTES,
        second=0,
        microsecond=0,
    )
    normalized_end = end.replace(second=0, microsecond=0)
    if normalized_end < end or normalized_end.minute % GOOGLE_CACHE_WINDOW_MINUTES:
        normalized_end += timedelta(
            minutes=GOOGLE_CACHE_WINDOW_MINUTES - normalized_end.minute % GOOGLE_CACHE_WINDOW_MINUTES
        )
    cache_key = (
        f"gcal:busy:{trainer.id}:{selection.revision}:"
        f"{normalized_start.isoformat()}:{normalized_end.isoformat()}"
    )
    cached = cache.get(cache_key)
    if isinstance(cached, list):
        cached_intervals = [(datetime.fromisoformat(item[0]), datetime.fromisoformat(item[1])) for item in cached]
        return _intersections(cached_intervals, [(start, end)]), "connected"
    try:
        calendar_ids = [
            decrypt_value(value, credential.encryption_key_id) for value in selection.encrypted_calendar_ids
        ]
        if not calendar_ids:
            return [], "no_calendars_selected"
        payload = _google_client().freebusy(
            credential,
            calendar_ids,
            time_min=normalized_start.isoformat().replace("+00:00", "Z"),
            time_max=normalized_end.isoformat().replace("+00:00", "Z"),
        )
        intervals = _merge(
            (
                datetime.fromisoformat(item["start"].replace("Z", "+00:00")),
                datetime.fromisoformat(item["end"].replace("Z", "+00:00")),
            )
            for item in payload
            if isinstance(item, dict) and item.get("start") and item.get("end")
        )
        cache.set(
            cache_key,
            [(a.isoformat(), b.isoformat()) for a, b in intervals],
            BUSY_CACHE_TTL_SECONDS,
        )
        register_busy_cache_key(selection.id, cache_key)
        return _intersections(intervals, [(start, end)]), "connected"
    except (GoogleCalendarError, ValueError) as exc:
        return [], getattr(exc, "code", "credential_error")


def _load_google_busy(trainer, start, end):
    close_old_connections()
    try:
        return _google_busy(trainer, start, end)
    finally:
        close_old_connections()


def _workshops(workspace_id, trainer_ids, start, end):
    schedules = (
        WorkshopSchedule.objects.filter(
            workspace_id=workspace_id,
            issue__issue_assignee__assignee_id__in=trainer_ids,
            starts_at__lt=end + timedelta(days=2),
            ends_at__gt=start - timedelta(days=1),
        )
        .select_related("issue", "project")
        .prefetch_related("issue__issue_assignee")
        .distinct()
    )
    result = {trainer_id: [] for trainer_id in trainer_ids}
    for schedule in schedules:
        block_start = schedule.starts_at - timedelta(
            minutes=schedule.preparation_minutes + schedule.travel_before_minutes
        )
        block_end = schedule.ends_at + timedelta(minutes=schedule.travel_after_minutes)
        for assignment in schedule.issue.issue_assignee.all():
            if assignment.assignee_id in result:
                clipped_start, clipped_end = max(block_start, start), min(block_end, end)
                if clipped_start < clipped_end:
                    result[assignment.assignee_id].append((clipped_start, clipped_end, schedule))
    return result


def _serialize_interval(start, end, kind, **extra):
    return {"start": start.isoformat(), "end": end.isoformat(), "kind": kind, **extra}


def calculate_workspace_capacity(*, workspace, viewer, start, end, trainer_ids=None):
    trainers = (
        TrainerProfile.objects.filter(workspace=workspace, status=TrainerProfile.Status.ACTIVE)
        .select_related("user")
        .prefetch_related("schedule_exceptions", "calendar_selection__credential")
    )
    if trainer_ids:
        trainers = trainers.filter(user_id__in=trainer_ids)
    trainers = list(trainers[:25])
    workshop_map = _workshops(workspace.id, [trainer.user_id for trainer in trainers], start, end)
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(trainers)))) as executor:
        google_results = {
            trainer.id: result
            for trainer, result in zip(
                trainers,
                executor.map(lambda trainer: _load_google_busy(trainer, start, end), trainers),
            )
        }
    visible_projects = set(
        ProjectMember.objects.filter(member=viewer, is_active=True).values_list("project_id", flat=True)
    )
    output = []
    for trainer in trainers:
        working = _working_intervals(trainer, start, end)
        google_busy, connection_status = google_results[trainer.id]
        workshop_records = workshop_map.get(trainer.user_id, [])
        workshop_intervals = [(a, b) for a, b, _ in workshop_records]
        combined_busy = _merge([*google_busy, *workshop_intervals])
        unavailable = _intersections(working, combined_busy)
        intervals = [_serialize_interval(a, b, "google_busy") for a, b in google_busy]
        for block_start, block_end, schedule in workshop_records:
            work_item = None
            if schedule.project_id in visible_projects:
                work_item = {
                    "id": str(schedule.issue_id),
                    "name": schedule.issue.name,
                    "project_id": str(schedule.project_id),
                }
            intervals.append(_serialize_interval(block_start, block_end, "workshop", work_item=work_item))
        conflicts = []
        for block_start, block_end, schedule in workshop_records:
            for overlap_start, overlap_end in _intersections([(block_start, block_end)], google_busy):
                conflicts.append(
                    _serialize_interval(
                        overlap_start, overlap_end, "google_overlap", work_item_id=str(schedule.issue_id)
                    )
                )
            for outside_start, outside_end in _subtract([(block_start, block_end)], working):
                conflicts.append(
                    _serialize_interval(
                        outside_start, outside_end, "outside_working_hours", work_item_id=str(schedule.issue_id)
                    )
                )
        for index, first in enumerate(workshop_records):
            for second in workshop_records[index + 1 :]:
                for overlap_start, overlap_end in _intersections([(first[0], first[1])], [(second[0], second[1])]):
                    conflicts.append(
                        _serialize_interval(
                            overlap_start, overlap_end, "workshop_overlap", work_item_id=str(first[2].issue_id)
                        )
                    )
        working_minutes = _minutes(working)
        unavailable_minutes = _minutes(unavailable)
        output.append(
            {
                "trainer_id": str(trainer.user_id),
                "display_name": trainer.user.display_name,
                "timezone": trainer.timezone,
                "connection_status": connection_status,
                "working_minutes": working_minutes,
                "google_busy_minutes": _minutes(_intersections(working, google_busy)),
                "workshop_minutes": _minutes(_intersections(working, workshop_intervals)),
                "unavailable_minutes": unavailable_minutes,
                "available_minutes": max(0, working_minutes - unavailable_minutes),
                "intervals": sorted(intervals, key=lambda item: (item["start"], item["kind"])),
                "conflicts": sorted(conflicts, key=lambda item: item["start"]),
            }
        )
    return output
