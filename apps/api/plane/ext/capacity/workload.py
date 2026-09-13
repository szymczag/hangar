# Copyright (c) 2026-present Maciej Szymczak and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

from plane.ext.models import WorkshopSession


def session_workload(workspace_id, trainer_ids, start, end):
    """Teaching effort in the requested period, independently of booking hours.

    Durations are summed per session (not merged): simultaneous assignments are
    still two commitments. A boundary session contributes only its intersecting
    delivery and buffer segments. Ticket and session counts count delivery in
    this period; buffers alone do not invent an additional workshop.
    """
    result = {
        trainer_id: {"workshop_count": 0, "session_count": 0, "delivery_minutes": 0, "buffer_minutes": 0}
        for trainer_id in trainer_ids
    }
    issues = {trainer_id: set() for trainer_id in trainer_ids}
    sessions = (
        WorkshopSession.objects.filter(
            schedule__workspace_id=workspace_id,
            trainers__id__in=trainer_ids,
            starts_at__lt=end + timedelta(days=2),
            ends_at__gt=start - timedelta(days=2),
        )
        .select_related("schedule")
        .prefetch_related("trainers")
        .distinct()
    )

    def overlap(a, b):
        return max(0, int((min(end, b) - max(start, a)).total_seconds() // 60))

    for session in sessions:
        delivery = overlap(session.starts_at, session.ends_at)
        buffers = overlap(
            session.starts_at - timedelta(minutes=session.preparation_minutes + session.travel_before_minutes),
            session.starts_at,
        ) + overlap(session.ends_at, session.ends_at + timedelta(minutes=session.travel_after_minutes))
        for trainer in session.trainers.all():
            if trainer.id not in result:
                continue
            row = result[trainer.id]
            row["delivery_minutes"] += delivery
            row["buffer_minutes"] += buffers
            if session.starts_at < end and session.ends_at > start:
                row["session_count"] += 1
                issues[trainer.id].add(session.schedule.issue_id)
    for trainer_id, row in result.items():
        row["workshop_count"] = len(issues[trainer_id])
    return result
