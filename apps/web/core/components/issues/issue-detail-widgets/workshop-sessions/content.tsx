/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { CarFront, Clock3, Timer, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { useMember } from "@/hooks/store/use-member";
import { blockedSpan, type TEditableSession } from "./helper";

const FIELD =
  "h-8 w-full min-w-0 rounded-sm border border-subtle bg-surface-1 px-2 text-body-xs-regular focus:border-accent-primary";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1">
      <span className="text-11 text-tertiary">{label}</span>
      {children}
    </label>
  );
}

function Minutes({
  label,
  icon: Icon,
  value,
  disabled,
  onChange,
  ariaLabel,
}: {
  label: string;
  icon: typeof Timer;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
  ariaLabel: string;
}) {
  return (
    <Field label={label}>
      <div className="relative">
        <Icon className="pointer-events-none absolute inset-y-0 left-2 my-auto size-3.5 text-tertiary" />
        <input
          aria-label={ariaLabel}
          type="number"
          min={0}
          max={1440}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(Number(event.target.value))}
          className={`${FIELD} pr-9 pl-7`}
        />
        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-11 text-placeholder">
          min
        </span>
      </div>
    </Field>
  );
}

type Props = {
  session: TEditableSession;
  index: number;
  total: number;
  assigneeIds: string[];
  disabled: boolean;
  timezone: string;
  onChange: (patch: Partial<TEditableSession>) => void;
  onRemove: () => void;
};

/**
 * One session, as a row of fields rather than a column of them.
 *
 * The container query is the point. This used to live in the work item's
 * properties sidebar, which is `md:w-1/4` with a fixed 120px label column, so a
 * `datetime-local` input -- whose intrinsic width the browser will not go below
 * -- had around 150px to render in and clipped. Here the widget lays itself out
 * against its own width, so the same markup works in the narrow peek panel and
 * across the full page.
 */
export function WorkshopSessionRow({
  session,
  index,
  total,
  assigneeIds,
  disabled,
  timezone,
  onChange,
  onRemove,
}: Props) {
  const { getUserDetails } = useMember();
  const span = blockedSpan(session);

  return (
    <div className="@container rounded-lg border border-subtle bg-layer-1 p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-body-xs-medium text-primary">
          Session {index + 1} of {total}
        </span>
        {!disabled && total > 1 ? (
          <Button variant="ghost" size="sm" aria-label={`Remove session ${index + 1}`} onClick={onRemove}>
            <Trash2 className="size-3.5" />
          </Button>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-3 @md:grid-cols-2">
        <Field label="Starts">
          <input
            aria-label={`Session ${index + 1} starts in ${timezone}`}
            type="datetime-local"
            value={session.starts_at}
            disabled={disabled}
            onChange={(event) => onChange({ starts_at: event.target.value })}
            className={FIELD}
          />
        </Field>
        <Field label="Ends">
          <input
            aria-label={`Session ${index + 1} ends in ${timezone}`}
            type="datetime-local"
            value={session.ends_at}
            disabled={disabled}
            onChange={(event) => onChange({ ends_at: event.target.value })}
            className={FIELD}
          />
        </Field>
      </div>

      {/* Buffers in their own row of three. Five fields in one two-column grid
          wrapped 2+2+1 and left "Travel after" stranded beside dead space, and
          the five-across breakpoint never fired: the body column is around
          700px even at a 1440 viewport, because the properties panel takes the
          rest. Grouping by meaning is balanced at every width the widget
          actually gets. */}
      <div className="mt-3 grid grid-cols-1 gap-3 @sm:grid-cols-3">
        <Minutes
          label="Preparation"
          icon={Timer}
          value={session.preparation_minutes}
          disabled={disabled}
          ariaLabel={`Session ${index + 1} preparation in minutes`}
          onChange={(value) => onChange({ preparation_minutes: value })}
        />
        <Minutes
          label="Travel before"
          icon={CarFront}
          value={session.travel_before_minutes}
          disabled={disabled}
          ariaLabel={`Session ${index + 1} travel before in minutes`}
          onChange={(value) => onChange({ travel_before_minutes: value })}
        />
        <Minutes
          label="Travel after"
          icon={CarFront}
          value={session.travel_after_minutes}
          disabled={disabled}
          ariaLabel={`Session ${index + 1} travel after in minutes`}
          onChange={(value) => onChange({ travel_after_minutes: value })}
        />
      </div>

      <div className="mt-3 flex flex-col gap-2 @2xl:flex-row @2xl:items-start @2xl:justify-between">
        <div className="min-w-0">
          <span className="text-11 text-tertiary">Trainers</span>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
            {assigneeIds.map((trainerId) => {
              const trainer = getUserDetails(trainerId);
              const checked = session.trainer_ids.includes(trainerId);
              return (
                <label key={trainerId} className="flex min-w-0 items-center gap-2 text-body-xs-regular text-secondary">
                  <input
                    type="checkbox"
                    checked={checked}
                    // The last trainer cannot be unchecked: a session with nobody
                    // on it is refused by the endpoint, and the refusal reads as a
                    // save failure rather than as this.
                    disabled={disabled || (checked && session.trainer_ids.length === 1)}
                    onChange={() =>
                      onChange({
                        trainer_ids: checked
                          ? session.trainer_ids.filter((id) => id !== trainerId)
                          : [...session.trainer_ids, trainerId],
                      })
                    }
                  />
                  <span className="truncate">{trainer?.display_name ?? trainer?.email ?? "Trainer"}</span>
                </label>
              );
            })}
            {!assigneeIds.length ? (
              <span className="text-11 text-danger-primary">Assign a trainer to this work item first</span>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 text-11 text-tertiary">
          <Clock3 className="size-3.5 shrink-0" />
          {span ? (
            <span>
              Blocks {span.from.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} –{" "}
              {span.until.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
            </span>
          ) : (
            <span>Set a start and end to see the blocked span</span>
          )}
        </div>
      </div>
    </div>
  );
}
