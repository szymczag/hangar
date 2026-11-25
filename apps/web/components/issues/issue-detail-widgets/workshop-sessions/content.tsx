/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ComponentType } from "react";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { InputField } from "@makeplane/propel/components/input-field";
import { ClockOutline, DeleteOutline, HourglassOutline, PinOutline } from "@makeplane/propel/icons";
import { useMember } from "@/hooks/store/use-member";
import { CalendarSyncBadges } from "./calendar-sync-badges";
import { blockedSpan, type TEditableSession } from "./helper";

function Minutes({
  label,
  icon,
  value,
  disabled,
  onChange,
  ariaLabel,
}: {
  label: string;
  icon: ComponentType<{ className?: string }>;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
  ariaLabel: string;
}) {
  return (
    <InputField
      size="md"
      orientation="vertical"
      label={label}
      aria-label={ariaLabel}
      type="number"
      min={0}
      max={1440}
      value={value}
      disabled={disabled}
      onChange={(event) => onChange(Number(event.target.value))}
      startIcon={<Icon icon={icon} />}
      endIcon={<span className="text-11 text-placeholder">min</span>}
    />
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
  const trainerName = (trainerId: string) => getUserDetails(trainerId)?.display_name ?? "Trainer";

  return (
    <div className="@container rounded-lg border border-subtle bg-layer-1 p-3">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-body-xs-medium text-primary">
          Session {index + 1} of {total}
        </span>
        {!disabled && total > 1 ? (
          <IconButton
            variant="ghost"
            size="sm"
            icon={<Icon icon={DeleteOutline} />}
            aria-label={`Remove session ${index + 1}`}
            onClick={onRemove}
          />
        ) : null}
      </div>

      <CalendarSyncBadges states={session.calendar_sync} nameFor={trainerName} />

      <div className="grid grid-cols-1 gap-3 @md:grid-cols-2">
        <InputField
          size="md"
          orientation="vertical"
          label="Starts"
          aria-label={`Session ${index + 1} starts in ${timezone}`}
          type="datetime-local"
          value={session.starts_at}
          disabled={disabled}
          onChange={(event) => onChange({ starts_at: event.target.value })}
        />
        <InputField
          size="md"
          orientation="vertical"
          label="Ends"
          aria-label={`Session ${index + 1} ends in ${timezone}`}
          type="datetime-local"
          value={session.ends_at}
          disabled={disabled}
          onChange={(event) => onChange({ ends_at: event.target.value })}
        />
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
          icon={HourglassOutline}
          value={session.preparation_minutes}
          disabled={disabled}
          ariaLabel={`Session ${index + 1} preparation in minutes`}
          onChange={(value) => onChange({ preparation_minutes: value })}
        />
        <Minutes
          label="Travel before"
          icon={PinOutline}
          value={session.travel_before_minutes}
          disabled={disabled}
          ariaLabel={`Session ${index + 1} travel before in minutes`}
          onChange={(value) => onChange({ travel_before_minutes: value })}
        />
        <Minutes
          label="Travel after"
          icon={PinOutline}
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
                <Checkbox
                  key={trainerId}
                  label={trainer?.display_name ?? trainer?.email ?? "Trainer"}
                  checked={checked}
                  // The last trainer cannot be unchecked: a session with nobody
                  // on it is refused by the endpoint, and the refusal reads as a
                  // save failure rather than as this.
                  disabled={disabled || (checked && session.trainer_ids.length === 1)}
                  onCheckedChange={() =>
                    onChange({
                      trainer_ids: checked
                        ? session.trainer_ids.filter((id) => id !== trainerId)
                        : [...session.trainer_ids, trainerId],
                    })
                  }
                />
              );
            })}
            {!assigneeIds.length ? (
              <span className="text-11 text-danger-primary">Assign a trainer to this work item first</span>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 text-11 text-tertiary">
          <ClockOutline className="size-3.5 shrink-0" />
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
