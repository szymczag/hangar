/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState, type FC } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CalendarClock, CarFront, CircleAlert, Clock3, Plus, Timer, Trash2, Users } from "lucide-react";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { useMember } from "@/hooks/store/use-member";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import { CapacityService, type TWorkshopSchedule, type TWorkshopSession } from "@/services/capacity.service";

const capacityService = new CapacityService();

type EditableSession = Omit<TWorkshopSession, "id"> & { localId: string };

const localValue = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
};

const newSession = (trainerIds: string[]): EditableSession => ({
  localId: crypto.randomUUID(),
  starts_at: "",
  ends_at: "",
  preparation_minutes: 0,
  travel_before_minutes: 0,
  travel_after_minutes: 0,
  trainer_ids: trainerIds,
});

const fieldClassName =
  "h-7.5 w-full min-w-0 rounded-sm border border-transparent bg-transparent px-2 text-body-xs-regular hover:border-subtle hover:bg-surface-2 focus:border-accent-primary focus:bg-surface-1";

function MinuteProperty({
  icon,
  label,
  value,
  disabled,
  onChange,
}: {
  icon: FC<{ className?: string }>;
  label: string;
  value: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <SidebarPropertyListItem icon={icon} label={label}>
      <div className="relative w-full">
        <input
          aria-label={`${label} in minutes`}
          type="number"
          min={0}
          max={1440}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(Number(event.target.value))}
          className={`${fieldClassName} pr-10`}
        />
        <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-11 text-placeholder">
          min
        </span>
      </div>
    </SidebarPropertyListItem>
  );
}

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueTypeId: string | null;
  assigneeIds: string[];
  isEditable: boolean;
};

export function WorkshopScheduleProperty({
  workspaceSlug,
  projectId,
  issueId,
  issueTypeId,
  assigneeIds,
  isEditable,
}: Props) {
  const { getTypeById } = useIssueTypes(workspaceSlug, projectId);
  const { getUserDetails } = useMember();
  const isWorkshop = getTypeById(issueTypeId)?.system_key === "workshop";
  const { data, error, isLoading, mutate } = useSWR<TWorkshopSchedule | null>(
    isWorkshop ? ["workshop-schedule", workspaceSlug, projectId, issueId] : null,
    () => capacityService.getWorkshopSchedule(workspaceSlug, projectId, issueId)
  );
  const [sessions, setSessions] = useState<EditableSession[]>([]);
  const [saving, setSaving] = useState(false);
  const viewerTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  useEffect(() => {
    const source = data?.sessions?.length
      ? data.sessions
      : data
        ? [
            {
              id: null,
              starts_at: data.starts_at,
              ends_at: data.ends_at,
              preparation_minutes: data.preparation_minutes,
              travel_before_minutes: data.travel_before_minutes,
              travel_after_minutes: data.travel_after_minutes,
              trainer_ids: assigneeIds,
            },
          ]
        : [];
    setSessions(
      source.map((session) => ({
        localId: session.id ?? crypto.randomUUID(),
        starts_at: localValue(session.starts_at),
        ends_at: localValue(session.ends_at),
        preparation_minutes: session.preparation_minutes,
        travel_before_minutes: session.travel_before_minutes,
        travel_after_minutes: session.travel_after_minutes,
        trainer_ids: session.trainer_ids,
      }))
    );
  }, [assigneeIds, data]);

  if (!isWorkshop) return null;

  const updateSession = (localId: string, patch: Partial<EditableSession>) =>
    setSessions((current) =>
      current.map((session) => (session.localId === localId ? { ...session, ...patch } : session))
    );

  const save = async () => {
    if (!sessions.length || sessions.some((session) => !session.starts_at || !session.ends_at)) return;
    setSaving(true);
    try {
      await capacityService.saveWorkshopSchedule(workspaceSlug, projectId, issueId, {
        sessions: sessions.map(({ localId: _localId, ...session }) => ({
          ...session,
          starts_at: new Date(session.starts_at).toISOString(),
          ends_at: new Date(session.ends_at).toISOString(),
        })),
      });
      await mutate();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workshop scheduled",
        message: `${sessions.length} ${sessions.length === 1 ? "session" : "sessions"} added to trainer capacity.`,
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Workshop not scheduled",
        message: "Check every session and make sure its trainers are active Workshop assignees.",
      });
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await capacityService.deleteWorkshopSchedule(workspaceSlug, projectId, issueId);
      setSessions([]);
      await mutate(null, { revalidate: false });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workshop schedule removed",
        message: "Trainer capacity has been updated.",
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Workshop schedule not removed",
        message: "Try again. The existing schedule is still active.",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <SidebarPropertyListItem icon={CalendarClock} label="Workshop sessions">
        <div className="flex w-full items-center justify-between gap-2 px-2">
          <span className="text-body-xs-regular text-secondary">
            {sessions.length ? `${sessions.length} scheduled` : "Not scheduled"}
          </span>
          {isEditable ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setSessions((current) => [...current, newSession(assigneeIds)])}
            >
              <Plus className="size-3.5" /> Add session
            </Button>
          ) : null}
        </div>
      </SidebarPropertyListItem>

      {sessions.map((session, index) => {
        const blockedFrom = session.starts_at
          ? new Date(
              new Date(session.starts_at).getTime() -
                (session.preparation_minutes + session.travel_before_minutes) * 60_000
            )
          : null;
        const blockedUntil = session.ends_at
          ? new Date(new Date(session.ends_at).getTime() + session.travel_after_minutes * 60_000)
          : null;
        const blockedLabel =
          blockedFrom && blockedUntil
            ? `${blockedFrom.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} – ${blockedUntil.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}`
            : "Set start and end";

        return (
          <div key={session.localId} className="contents">
            <SidebarPropertyListItem icon={CalendarClock} label={`Session ${index + 1}`}>
              <div className="flex w-full items-center justify-between gap-2 px-2">
                <span className="text-11 font-medium text-primary">
                  {index + 1} of {sessions.length}
                </span>
                {isEditable && sessions.length > 1 ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={`Remove session ${index + 1}`}
                    onClick={() => setSessions((current) => current.filter((item) => item.localId !== session.localId))}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                ) : null}
              </div>
            </SidebarPropertyListItem>
            <SidebarPropertyListItem icon={CalendarClock} label="Starts">
              <input
                aria-label={`Session ${index + 1} starts in ${viewerTimezone}`}
                type="datetime-local"
                value={session.starts_at}
                disabled={!isEditable}
                onChange={(event) => updateSession(session.localId, { starts_at: event.target.value })}
                className={fieldClassName}
              />
            </SidebarPropertyListItem>
            <SidebarPropertyListItem icon={CalendarClock} label="Ends">
              <input
                aria-label={`Session ${index + 1} ends in ${viewerTimezone}`}
                type="datetime-local"
                value={session.ends_at}
                disabled={!isEditable}
                onChange={(event) => updateSession(session.localId, { ends_at: event.target.value })}
                className={fieldClassName}
              />
            </SidebarPropertyListItem>
            <MinuteProperty
              icon={Timer}
              label="Preparation"
              value={session.preparation_minutes}
              disabled={!isEditable}
              onChange={(value) => updateSession(session.localId, { preparation_minutes: value })}
            />
            <MinuteProperty
              icon={CarFront}
              label="Travel before"
              value={session.travel_before_minutes}
              disabled={!isEditable}
              onChange={(value) => updateSession(session.localId, { travel_before_minutes: value })}
            />
            <MinuteProperty
              icon={CarFront}
              label="Travel after"
              value={session.travel_after_minutes}
              disabled={!isEditable}
              onChange={(value) => updateSession(session.localId, { travel_after_minutes: value })}
            />
            <SidebarPropertyListItem icon={Users} label="Trainers">
              <div className="flex w-full flex-col gap-1 px-2 py-1">
                {assigneeIds.map((trainerId) => {
                  const trainer = getUserDetails(trainerId);
                  const checked = session.trainer_ids.includes(trainerId);
                  return (
                    <label
                      key={trainerId}
                      className="flex min-w-0 items-center gap-2 text-body-xs-regular text-secondary"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        disabled={!isEditable || (checked && session.trainer_ids.length === 1)}
                        onChange={() =>
                          updateSession(session.localId, {
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
                  <span className="text-11 text-danger-primary">Assign a trainer first</span>
                ) : null}
              </div>
            </SidebarPropertyListItem>
            <SidebarPropertyListItem icon={Clock3} label="Trainer blocked">
              <div
                className="w-full px-2 py-1 text-body-xs-regular whitespace-normal text-secondary"
                title={blockedLabel}
              >
                {blockedLabel}
              </div>
            </SidebarPropertyListItem>
          </div>
        );
      })}

      {error ? (
        <SidebarPropertyListItem icon={CircleAlert} label="Schedule status">
          <p role="alert" className="px-2 py-1 text-body-xs-regular whitespace-normal text-danger-primary">
            Schedule could not be loaded. Try again.
          </p>
        </SidebarPropertyListItem>
      ) : null}
      <SidebarPropertyListItem icon={CalendarClock} label="Schedule actions">
        {isEditable ? (
          <div className="flex w-full flex-wrap gap-2">
            <Button
              variant="primary"
              size="sm"
              loading={saving || isLoading}
              disabled={
                !sessions.length ||
                sessions.some((session) => !session.starts_at || !session.ends_at || !session.trainer_ids.length) ||
                Boolean(error)
              }
              onClick={save}
            >
              Save schedule
            </Button>
            {data ? (
              <Button variant="secondary" size="sm" disabled={saving} onClick={remove}>
                Remove all
              </Button>
            ) : null}
          </div>
        ) : (
          <span className="px-2 text-11 text-placeholder">Times shown in {viewerTimezone}</span>
        )}
      </SidebarPropertyListItem>
    </>
  );
}
