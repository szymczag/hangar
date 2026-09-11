/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTrainerCapacity } from "@/services/capacity.service";
import {
  CAPACITY_INTERVAL_LAYERS,
  availableRanges,
  formatRange,
  intervalLabel,
  intervalPosition,
} from "../shared/capacity-timeline.utils";

export function TrainerDayTimeline({
  trainer,
  dayStart,
  dayEnd,
}: {
  trainer: TTrainerCapacity;
  dayStart: Date;
  dayEnd: Date;
}) {
  const free = availableRanges(trainer.intervals, dayStart, dayEnd);
  return (
    <div>
      <div className="relative h-20 min-w-[680px] overflow-hidden rounded-md border border-subtle bg-surface-2">
        {/* Midnight anchors to the right edge instead of sitting at `left: 100%`
            pulled back by a transform. A transform moves what is drawn, not the
            layout box, so the old version left a label twenty-seven pixels wide
            hanging past the end of the strip: invisible behind `overflow-hidden`,
            and enough to make the element report a scroll width wider than itself. */}
        {[0, 3, 6, 9, 12, 15, 18, 21, 24].map((hour) => (
          <span
            key={hour}
            aria-hidden="true"
            className="absolute top-0 bottom-0 z-0 border-l border-subtle text-[9px] text-placeholder"
            style={hour === 24 ? { right: 0 } : { left: `${(hour / 24) * 100}%` }}
          >
            <span className={hour === 24 ? "pr-1" : "px-1"}>{String(hour).padStart(2, "0")}:00</span>
          </span>
        ))}
        {free.map((range) => {
          const position = intervalPosition(range, dayStart, dayEnd);
          if (!position) return null;
          const label = `Available ${formatRange(range)}`;
          return (
            <span
              key={`available-${range.start}-${range.end}`}
              role="img"
              aria-label={label}
              title={label}
              className="bg-success-secondary ring-success-primary/30 absolute top-6 bottom-2 z-10 rounded-sm ring-1 ring-inset"
              style={position}
            />
          );
        })}
        {CAPACITY_INTERVAL_LAYERS.filter((kind) => kind !== "working").flatMap((kind) =>
          trainer.intervals
            .filter((interval) => interval.kind === kind)
            .map((interval) => {
              const position = intervalPosition(interval, dayStart, dayEnd);
              if (!position) return null;
              const className =
                interval.kind === "google_busy"
                  ? "bg-neutral-500/70"
                  : interval.kind === "workshop_hold"
                    ? "bg-warning-primary/70"
                    : "bg-accent-primary/80";
              const label = intervalLabel(interval);
              return (
                <button
                  key={`${interval.kind}-${interval.start}-${interval.end}-${interval.work_item?.id ?? "anonymous"}`}
                  type="button"
                  aria-label={`${label}, ${formatRange(interval)}`}
                  title={`${label} · ${formatRange(interval)}`}
                  className={`absolute top-6 bottom-2 z-20 min-w-1 rounded-sm ${className}`}
                  style={position}
                />
              );
            })
        )}
        {trainer.conflicts.map((conflict) => {
          const position = intervalPosition(conflict, dayStart, dayEnd);
          if (!position) return null;
          return (
            <span
              key={`${conflict.kind}-${conflict.start}-${conflict.end}`}
              role="img"
              aria-label={`Conflict: ${conflict.kind.replaceAll("_", " ")}`}
              title={`Conflict: ${conflict.kind.replaceAll("_", " ")}`}
              className="border-danger-primary absolute top-5 bottom-1 z-30 min-w-1 rounded-sm border"
              style={{
                ...position,
                backgroundImage:
                  "repeating-linear-gradient(135deg, transparent, transparent 4px, rgb(var(--color-danger-primary)) 4px, rgb(var(--color-danger-primary)) 6px)",
              }}
            />
          );
        })}
      </div>
      <p className="mt-2 text-11 whitespace-normal text-secondary">
        <span className="font-medium text-primary">Available:</span>{" "}
        {free.length ? free.map(formatRange).join(", ") : "No free time in booking hours"}
      </p>
    </div>
  );
}
