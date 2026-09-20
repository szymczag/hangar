/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TCalendarSyncState } from "@/services/capacity.service";

/**
 * What the shared training calendar currently says about this session.
 *
 * One line per trainer rather than one verdict per session: a session delivered
 * by two people can have one invitation sent and the other blocked on somebody
 * who never connected Google, and "partly synced" tells nobody whom to chase.
 *
 * Renders nothing at all when write-back is off or the session is new, because
 * an empty state here would be a promise the feature is not making.
 */

const COPY: Record<TCalendarSyncState["state"], { label: string; tone: string }> = {
  synced: { label: "In the training calendar", tone: "text-secondary" },
  pending: { label: "Adding to the training calendar…", tone: "text-secondary" },
  failed: { label: "Not added — will keep trying", tone: "text-danger-primary" },
  blocked_no_writer: {
    label: "Not added — no account is connected to write to the training calendar",
    tone: "text-danger-primary",
  },
  blocked: { label: "Not added", tone: "text-danger-primary" },
};

// Why a blocked row is blocked, in terms of what somebody can do about it.
const REASONS: Record<string, string> = {
  trainer_not_connected: "this trainer has not connected Google",
  writer_changed: "the writing account changed after this was planned; save the schedule again",
  rule_removed: "the training calendar rule was removed",
};

export function CalendarSyncBadges({
  states,
  nameFor,
}: {
  states: TCalendarSyncState[] | undefined;
  nameFor: (trainerId: string) => string;
}) {
  if (!states?.length) return null;
  return (
    <ul className="mt-1 flex flex-col gap-0.5">
      {states.map((state) => {
        const copy = COPY[state.state] ?? COPY.blocked;
        const reason = state.state === "blocked" ? REASONS[state.last_error_code] : undefined;
        return (
          <li key={state.trainer_id} className={`text-11 ${copy.tone}`}>
            {nameFor(state.trainer_id)}: {copy.label}
            {reason ? ` — ${reason}` : ""}
          </li>
        );
      })}
    </ul>
  );
}
