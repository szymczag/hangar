/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight, CircleAlert } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Spinner } from "@plane/ui";
import type { TTrainerCapacity, TTrainerProfile } from "@/services/capacity.service";
import {
  availableRanges,
  clippedRanges,
  dayBounds,
  intervalPosition,
  formatRange,
  rangeMinutes,
} from "../shared/capacity-timeline.utils";
import {
  DAY_KEYS,
  DAY_LABELS,
  availabilityCopy,
  errorMessage,
  formatMinutes,
  shiftWeek,
} from "../shared/capacity-format.utils";
import type { useCapacityData } from "../shared/use-capacity-data";
import { TrainerDayTimeline } from "./trainer-day-timeline";

function trainerDayMetrics(trainer: TTrainerCapacity, dayStart: Date, dayEnd: Date) {
  const free = availableRanges(trainer.intervals, dayStart, dayEnd);
  const rangesFor = (kind: "working" | "google_busy" | "workshop" | "workshop_hold") =>
    clippedRanges(
      trainer.intervals.filter((interval) => interval.kind === kind),
      dayStart,
      dayEnd
    );
  const conflicts = trainer.conflicts.filter((conflict) => intervalPosition(conflict, dayStart, dayEnd));
  return {
    free,
    freeMinutes: rangeMinutes(free),
    workingMinutes: rangeMinutes(rangesFor("working")),
    googleBusyMinutes: rangeMinutes(rangesFor("google_busy")),
    workshopMinutes: rangeMinutes(rangesFor("workshop")),
    holdMinutes: rangeMinutes(rangesFor("workshop_hold")),
    conflicts,
  };
}

type Props = {
  /** Everything the ledger reads comes from one hook, so the caller owns the week. */
  data: ReturnType<typeof useCapacityData>;
  isAdmin: boolean;
  ownProfile: TTrainerProfile | null | undefined;
  /** Opens the schedule editor for a trainer; the caller decides where that lives. */
  onManageSchedule: (trainerId: string) => void;
  /** Opting in is a personal action. `/capacity/team` passes null and links instead. */
  becomeTrainer: { onClick: () => void; busy: boolean } | null;
};

/**
 * The capacity ledger: who has time this week, and what is already on it.
 *
 * Lifted out of the single capacity page so `/capacity/team` and the existing
 * `/capacity` can both render it during the changeover, rather than the same
 * three hundred lines living in two files for a release.
 *
 * The selected day is local state, because it is this section's own tab and
 * nothing else has an opinion about it. The week is not: the planner reads the
 * same window, so it stays with the caller's hook.
 */
export function CapacityLedger({ data, isAdmin, ownProfile, onManageSchedule, becomeTrainer }: Props) {
  const {
    capacity,
    capacityError,
    capacityLoading,
    trainerPage,
    trainersLoading,
    weekStart,
    setWeekStart,
    trainerCursor,
    setTrainerCursor,
    cursorHistory,
    setCursorHistory,
    refreshCapacity,
    weekEnd,
  } = data;
  const [selectedDayIndex, setSelectedDayIndex] = useState(() => {
    const day = new Date().getDay();
    return day === 0 || day === 6 ? 0 : day - 1;
  });
  const selectedDay = useMemo(() => dayBounds(weekStart, selectedDayIndex), [selectedDayIndex, weekStart]);
  const hasActiveProfile = ownProfile?.status === "active";

  return (
    <section className="overflow-hidden rounded-xl border border-subtle bg-surface-1">
      <div className="flex flex-col justify-between gap-4 border-b border-subtle px-5 py-5 md:flex-row md:items-end">
        <div>
          <div className="mb-2 flex items-center gap-2 text-11 font-semibold tracking-[0.16em] text-placeholder uppercase">
            <CalendarClock className="size-3.5" /> Capacity ledger
          </div>
          <h1 className="text-xl font-semibold text-primary">Find a trainer and time.</h1>
          <p className="mt-1 max-w-2xl text-body-sm-regular text-secondary">
            Working hours, anonymous Google busy time, and scheduled workshops in one planning rail.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {becomeTrainer && !hasActiveProfile ? (
            <Button variant="primary" size="sm" loading={becomeTrainer.busy} onClick={becomeTrainer.onClick}>
              {ownProfile ? "Reactivate trainer" : "Become a trainer"}
            </Button>
          ) : null}
          <Button
            variant="secondary"
            size="sm"
            aria-label="Previous week"
            onClick={() => setWeekStart((current) => shiftWeek(current, -1))}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <div className="min-w-44 text-center text-body-xs-medium">
            {weekStart.toLocaleDateString(undefined, { day: "numeric", month: "short" })} –{" "}
            {new Date(weekEnd.getTime() - 1).toLocaleDateString(undefined, {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </div>
          <Button
            variant="secondary"
            size="sm"
            aria-label="Next week"
            onClick={() => setWeekStart((current) => shiftWeek(current, 1))}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
      {(capacityLoading || trainersLoading) && !capacity ? (
        <div className="grid min-h-56 place-items-center">
          <Spinner />
        </div>
      ) : capacityError && !capacity ? (
        <div role="alert" className="flex min-h-56 flex-col items-center justify-center gap-2 px-5 text-center">
          <CircleAlert className="size-6 text-danger-primary" />
          <h2 className="text-body-sm-medium">Capacity could not be loaded</h2>
          <p className="text-body-xs-regular text-secondary">{errorMessage(capacityError, "Try again shortly.")}</p>
          <Button variant="secondary" size="sm" onClick={() => refreshCapacity()}>
            Retry
          </Button>
        </div>
      ) : capacity?.trainers.length ? (
        <div>
          <div className="border-b border-subtle bg-surface-1 px-5 py-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7" aria-label="Choose planning day">
              {DAY_KEYS.map((day, index) => {
                const bounds = dayBounds(weekStart, index);
                const availableCount = capacity.trainers.filter(
                  (trainer) => availableRanges(trainer.intervals, bounds.start, bounds.end).length > 0
                ).length;
                const conflictCount = capacity.trainers.reduce(
                  (count, trainer) =>
                    count +
                    trainer.conflicts.filter((conflict) => intervalPosition(conflict, bounds.start, bounds.end)).length,
                  0
                );
                const selected = selectedDayIndex === index;
                return (
                  <button
                    key={day}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => setSelectedDayIndex(index)}
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
          </div>
          <div className="divide-y divide-subtle lg:hidden">
            {capacity.trainers.map((trainer) => {
              const metrics = trainerDayMetrics(trainer, selectedDay.start, selectedDay.end);
              return (
                <article key={trainer.trainer_id} className="space-y-3 px-5 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-body-sm-medium text-primary">{trainer.display_name}</h2>
                      <p className="mt-1 text-11 text-secondary">
                        {availabilityCopy(trainer.availability_status)} · {trainer.timezone}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-body-sm-medium text-primary tabular-nums">
                        {formatMinutes(metrics.freeMinutes)} free
                      </div>
                      <div className="text-11 text-placeholder">of {formatMinutes(metrics.workingMinutes)}</div>
                    </div>
                  </div>
                  <div className="rounded-md border border-subtle bg-surface-2 px-3 py-2 text-body-xs-regular whitespace-normal">
                    <span className="font-medium text-primary">Available:</span>{" "}
                    <span className="text-secondary">
                      {metrics.free.length ? metrics.free.map(formatRange).join(", ") : "No free time in booking hours"}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-11 text-secondary">
                    <span>Google busy {formatMinutes(metrics.googleBusyMinutes)}</span>
                    <span>Workshops {formatMinutes(metrics.workshopMinutes)}</span>
                    {metrics.holdMinutes ? <span>Holds {formatMinutes(metrics.holdMinutes)}</span> : null}
                    {metrics.conflicts.length ? (
                      <span className="inline-flex items-center gap-1 text-danger-primary">
                        <CircleAlert className="size-3" /> {metrics.conflicts.length} conflict
                        {metrics.conflicts.length === 1 ? "" : "s"}
                      </span>
                    ) : null}
                    {isAdmin || trainer.trainer_id === ownProfile?.user_id ? (
                      <button
                        type="button"
                        className="ml-auto text-accent-primary"
                        onClick={() => onManageSchedule(trainer.trainer_id)}
                      >
                        Manage schedule
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
          <div className="hidden overflow-x-auto lg:block">
            <div className="min-w-[1180px]">
              {capacityError ? (
                <div
                  role="status"
                  className="bg-warning-secondary border-b border-subtle px-5 py-2 text-11 text-secondary"
                >
                  Availability is being refreshed. The last request was rate limited or temporarily unavailable.
                </div>
              ) : null}
              <div className="grid grid-cols-[210px_1fr_150px] items-end gap-5 border-b border-subtle bg-surface-2 px-5 py-3">
                <div className="text-11 font-semibold tracking-wide text-placeholder uppercase">Trainer</div>
                <div className="text-11 font-semibold tracking-wide text-placeholder uppercase">
                  {selectedDay.start.toLocaleDateString(undefined, {
                    weekday: "long",
                    day: "numeric",
                    month: "long",
                  })}
                </div>
                <div className="text-right text-11 font-semibold tracking-wide text-placeholder uppercase">
                  Day capacity
                </div>
              </div>
              <div className="divide-y divide-subtle">
                {capacity.trainers.map((trainer) => {
                  const metrics = trainerDayMetrics(trainer, selectedDay.start, selectedDay.end);
                  return (
                    <article
                      key={trainer.trainer_id}
                      className="grid grid-cols-[210px_1fr_150px] items-center gap-5 px-5 py-5"
                    >
                      <div>
                        <h2 className="text-body-sm-medium text-primary">{trainer.display_name}</h2>
                        <p className="mt-1 text-11 text-secondary">
                          {availabilityCopy(trainer.availability_status)} · {trainer.timezone}
                        </p>
                      </div>
                      <div>
                        <TrainerDayTimeline trainer={trainer} dayStart={selectedDay.start} dayEnd={selectedDay.end} />
                        <div className="mt-2 flex gap-4 text-11 text-secondary">
                          <span>Google {formatMinutes(metrics.googleBusyMinutes)}</span>
                          <span>Workshops {formatMinutes(metrics.workshopMinutes)}</span>
                          {metrics.holdMinutes ? <span>Holds {formatMinutes(metrics.holdMinutes)}</span> : null}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-semibold text-primary tabular-nums">
                          {formatMinutes(metrics.freeMinutes)}
                        </div>
                        <div className="text-11 text-placeholder">of {formatMinutes(metrics.workingMinutes)} free</div>
                        {metrics.conflicts.length ? (
                          <div className="mt-1 inline-flex items-center gap-1 text-11 text-danger-primary">
                            <CircleAlert className="size-3" /> {metrics.conflicts.length} conflict
                            {metrics.conflicts.length === 1 ? "" : "s"}
                          </div>
                        ) : null}
                        {isAdmin || trainer.trainer_id === ownProfile?.user_id ? (
                          <button
                            type="button"
                            className="mt-2 text-11 text-accent-primary"
                            onClick={() => onManageSchedule(trainer.trainer_id)}
                          >
                            Manage schedule
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
              <div
                className="flex flex-wrap items-center gap-4 border-t border-subtle bg-surface-2 px-5 py-3 text-11 text-secondary"
                aria-label="Timeline legend"
              >
                <span className="inline-flex items-center gap-1.5">
                  <span className="bg-success-secondary ring-success-primary/30 size-2.5 rounded-sm ring-1" />
                  Available
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="bg-neutral-500/55 size-2.5 rounded-sm" />
                  Google busy
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-2.5 rounded-sm bg-accent-primary/70" />
                  Workshop
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="border-danger-primary bg-danger-secondary size-2.5 rounded-sm border" />
                  Conflict
                </span>
                <span className="ml-auto">Times shown in {Intl.DateTimeFormat().resolvedOptions().timeZone}</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex min-h-56 flex-col items-center justify-center gap-3 px-5 text-center">
          <CalendarClock className="size-8 text-placeholder" />
          <div>
            <h2 className="text-body-sm-medium">No trainers yet</h2>
            <p className="mt-1 text-body-xs-regular text-secondary">Opt in to start the workspace capacity ledger.</p>
          </div>
          {becomeTrainer && !hasActiveProfile ? (
            <Button variant="primary" loading={becomeTrainer.busy} onClick={becomeTrainer.onClick}>
              {ownProfile ? "Reactivate trainer" : "Become a trainer"}
            </Button>
          ) : null}
        </div>
      )}
      {(cursorHistory.length > 0 || trainerPage?.next_cursor) && (
        <div className="flex items-center justify-end gap-2 border-t border-subtle px-5 py-3">
          <Button
            variant="secondary"
            size="sm"
            disabled={cursorHistory.length === 0}
            onClick={() => {
              setTrainerCursor(cursorHistory[cursorHistory.length - 1]);
              setCursorHistory((current) => current.slice(0, -1));
            }}
          >
            Previous trainers
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!trainerPage?.next_cursor}
            onClick={() => {
              setCursorHistory((current) => [...current, trainerCursor]);
              setTrainerCursor(trainerPage?.next_cursor ?? undefined);
            }}
          >
            Next trainers
          </Button>
        </div>
      )}
    </section>
  );
}
