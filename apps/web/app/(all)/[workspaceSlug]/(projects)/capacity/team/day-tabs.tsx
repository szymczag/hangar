/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTrainerCapacity } from "@/services/capacity.service";
import { availableRanges, dayBounds, intervalPosition } from "../shared/capacity-timeline.utils";
import { DAY_KEYS, DAY_LABELS } from "../shared/capacity-format.utils";

type Props = {
  weekStart: Date;
  trainers: TTrainerCapacity[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  /** Saturday and Sunday get a tab only when asked for. */
  showWeekends: boolean;
  /** Absent on a ledger that does not offer the choice. */
  onShowWeekends?: (next: boolean) => void;
};

/**
 * Which day of the week the rail below is showing.
 *
 * Weekends are hidden by default: training runs on weekdays, and two dead tabs
 * took a seventh of a row whose whole job is the week's shape. They are a toggle
 * rather than a removal because a weekend course is a real thing -- it is simply
 * not what this row is scanned for.
 *
 * Lifted out of the ledger, which is long enough that adding this to it made it
 * longer still. The counts are the reason each tab exists, so they are computed
 * here rather than passed in already summed.
 */
export function DayTabs({ weekStart, trainers, selectedIndex, onSelect, showWeekends, onShowWeekends }: Props) {
  const visibleDays = DAY_KEYS.slice(0, showWeekends ? 7 : 5);

  return (
    <div className="border-b border-subtle bg-surface-1 px-5 py-3">
      <div
        className={`grid grid-cols-2 gap-2 sm:grid-cols-4 ${showWeekends ? "lg:grid-cols-7" : "lg:grid-cols-5"}`}
        aria-label="Choose planning day"
      >
        {visibleDays.map((day, index) => {
          const bounds = dayBounds(weekStart, index);
          const availableCount = trainers.filter(
            (trainer) => availableRanges(trainer.intervals, bounds.start, bounds.end).length > 0
          ).length;
          const conflictCount = trainers.reduce(
            (count, trainer) =>
              count +
              trainer.conflicts.filter((conflict) => intervalPosition(conflict, bounds.start, bounds.end)).length,
            0
          );
          const selected = selectedIndex === index;
          return (
            <button
              key={day}
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(index)}
              className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                selected
                  ? "border-accent-primary bg-accent-primary/10"
                  : "border-subtle bg-surface-2 hover:border-strong"
              }`}
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="text-body-xs-medium text-primary">{DAY_LABELS[index]}</span>
                <span className="text-11 text-placeholder">
                  {bounds.start.toLocaleDateString(undefined, { day: "numeric", month: "short" })}
                </span>
              </span>
              <span className="mt-1 block text-11 text-secondary">
                {availableCount} available
                {conflictCount ? <span className="text-danger-primary"> · {conflictCount} conflicts</span> : null}
              </span>
            </button>
          );
        })}
      </div>
      {onShowWeekends ? (
        <button
          type="button"
          aria-pressed={showWeekends}
          className="mt-2 text-11 text-accent-primary"
          onClick={() => onShowWeekends(!showWeekends)}
        >
          {showWeekends ? "Hide weekends" : "Show weekends"}
        </button>
      ) : null}
    </div>
  );
}
