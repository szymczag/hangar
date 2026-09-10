/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TWorkshopSchedule, TWorkshopSession } from "@/services/capacity.service";

/** A session being edited, before it has an id from the server. */
export type TEditableSession = Omit<TWorkshopSession, "id"> & { localId: string };

/** The id the sessions section is anchored on, so the summary can scroll to it. */
export const WORKSHOP_SESSIONS_ANCHOR = "workshop-sessions";

/**
 * An ISO instant as the value a `datetime-local` input expects.
 *
 * That input has no timezone: it reads and writes wall-clock time in whatever
 * zone the browser is in, so the offset has to be folded in on the way out and
 * back out again on the way in.
 */
export const localValue = (value?: string | null): string => {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
};

export const newSession = (trainerIds: string[]): TEditableSession => ({
  localId: crypto.randomUUID(),
  starts_at: "",
  ends_at: "",
  preparation_minutes: 0,
  travel_before_minutes: 0,
  travel_after_minutes: 0,
  trainer_ids: trainerIds,
});

/**
 * The schedule as a list of editable sessions.
 *
 * A schedule saved before multi-session support has its times on the schedule
 * itself rather than in `sessions`, so it is presented as a single session --
 * the same shape the editor writes back, which is what lets an old schedule be
 * edited without a migration step.
 */
export function toEditableSessions(
  schedule: TWorkshopSchedule | null | undefined,
  assigneeIds: string[]
): TEditableSession[] {
  const source: TWorkshopSession[] = schedule?.sessions?.length
    ? schedule.sessions
    : schedule
      ? [
          {
            id: null,
            starts_at: schedule.starts_at,
            ends_at: schedule.ends_at,
            preparation_minutes: schedule.preparation_minutes,
            travel_before_minutes: schedule.travel_before_minutes,
            travel_after_minutes: schedule.travel_after_minutes,
            trainer_ids: assigneeIds,
          },
        ]
      : [];

  return source.map((session) => ({
    localId: session.id ?? crypto.randomUUID(),
    starts_at: localValue(session.starts_at),
    ends_at: localValue(session.ends_at),
    preparation_minutes: session.preparation_minutes,
    travel_before_minutes: session.travel_before_minutes,
    travel_after_minutes: session.travel_after_minutes,
    trainer_ids: session.trainer_ids,
  }));
}

/** The span a session actually costs a trainer, buffers included. */
export function blockedSpan(session: TEditableSession): { from: Date; until: Date } | null {
  if (!session.starts_at || !session.ends_at) return null;
  const from = new Date(
    new Date(session.starts_at).getTime() - (session.preparation_minutes + session.travel_before_minutes) * 60_000
  );
  const until = new Date(new Date(session.ends_at).getTime() + session.travel_after_minutes * 60_000);
  return { from, until };
}

/** Whether every session carries the fields the endpoint requires. */
export const isSchedulable = (sessions: TEditableSession[]): boolean =>
  sessions.length > 0 &&
  sessions.every((session) => session.starts_at && session.ends_at && session.trainer_ids.length > 0);
