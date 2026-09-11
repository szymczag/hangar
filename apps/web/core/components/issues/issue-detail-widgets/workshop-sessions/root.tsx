/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { CalendarClock, ChevronRight, CircleAlert, Plus } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { useMember } from "@/hooks/store/use-member";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import { CapacityService, type TWorkshopSchedule } from "@/services/capacity.service";
import { WorkshopSessionRow } from "./content";
import {
  isSchedulable,
  newSession,
  toEditableSessions,
  WORKSHOP_SESSIONS_ANCHOR,
  type TEditableSession,
} from "./helper";

const capacityService = new CapacityService();

/** Shared with the sidebar summary, so both read one cache entry. */
export const workshopScheduleKey = (workspaceSlug: string, projectId: string, issueId: string) =>
  ["workshop-schedule", workspaceSlug, projectId, issueId] as const;

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueTypeId: string | null;
  assigneeIds: string[];
  disabled?: boolean;
};

/**
 * Workshop sessions, as a section of the work item rather than a property of it.
 *
 * It lived in the properties sidebar and could not fit there: seven stacked
 * label/value rows per session, in a column `md:w-1/4` wide whose label gutter
 * is a fixed 120px, against `datetime-local` inputs the browser will not shrink
 * below roughly the same width. Three sessions produced twenty-one rows, none of
 * them legible.
 *
 * Sitting beside sub-work-items, links and attachments it gets the body's full
 * width, and because it is mounted from `IssueDetailWidgetCollapsibles` it
 * appears in the peek panel and the full-screen peek too -- neither of which
 * rendered it at all before.
 *
 * Open state is local rather than the widget store's `openWidgets`, because that
 * store is keyed by `TWorkItemWidgets`, a closed union in upstream
 * `packages/types`. Keeping it local avoids widening an upstream type for a fork
 * feature.
 */
export function WorkshopSessionsCollapsible({
  workspaceSlug,
  projectId,
  issueId,
  issueTypeId,
  assigneeIds,
  disabled = false,
}: Props) {
  const { getTypeById } = useIssueTypes(workspaceSlug, projectId);
  const { getUserDetails } = useMember();
  const isWorkshop = getTypeById(issueTypeId)?.system_key === "workshop";

  /**
   * Trainers in a fixed order, by name.
   *
   * `assignee_ids` arrives from `ArrayAgg("assignee_id", distinct=True)` with no
   * `ordering`, and `array_agg(DISTINCT ...)` makes no promise about the order it
   * returns. So the checkbox list reshuffled between requests -- caught by a
   * screenshot of this panel that would not hold still, and visible to anyone
   * who reloads a workshop and finds the trainers swapped.
   *
   * Sorted here rather than in the query because that annotation is upstream's
   * and appears seventeen times across three files; every work item in Plane
   * inherits the same unordered list. This is the fork's own surface, and by
   * name matches the order the capacity ledger now uses.
   */
  const orderedAssigneeIds = useMemo(
    () =>
      // ES2022 is the web app's current target; the copied array keeps sort() mutation local.
      // oxlint-disable-next-line unicorn/no-array-sort
      [...assigneeIds].sort((left, right) => {
        const name = (id: string) => getUserDetails(id)?.display_name ?? id;
        return name(left).localeCompare(name(right)) || left.localeCompare(right);
      }),
    [assigneeIds, getUserDetails]
  );

  const { data, error, isLoading, mutate } = useSWR<TWorkshopSchedule | null>(
    isWorkshop ? workshopScheduleKey(workspaceSlug, projectId, issueId) : null,
    () => capacityService.getWorkshopSchedule(workspaceSlug, projectId, issueId)
  );

  const [sessions, setSessions] = useState<TEditableSession[]>([]);
  const [saving, setSaving] = useState(false);
  const [isOpen, setIsOpen] = useState(true);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  // The ordered list here too: a schedule saved before multi-session support has
  // its trainers synthesised from the assignees, and that list is written back on
  // the next save.
  useEffect(() => setSessions(toEditableSessions(data, orderedAssigneeIds)), [orderedAssigneeIds, data]);

  if (!isWorkshop) return null;

  const updateSession = (localId: string, patch: Partial<TEditableSession>) =>
    setSessions((current) =>
      current.map((session) => (session.localId === localId ? { ...session, ...patch } : session))
    );

  const save = async () => {
    if (!isSchedulable(sessions)) return;
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
    <section id={WORKSHOP_SESSIONS_ANCHOR} className="py-2">
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
        className="flex w-full items-center gap-2 rounded-sm py-1 text-left hover:bg-surface-2"
      >
        <ChevronRight className={`size-4 shrink-0 text-tertiary transition-transform ${isOpen ? "rotate-90" : ""}`} />
        <CalendarClock className="size-4 shrink-0 text-tertiary" />
        <span className="text-body-sm-medium text-primary">Workshop sessions</span>
        <span className="text-body-xs-regular text-tertiary">
          {sessions.length ? `${sessions.length}` : "none scheduled"}
        </span>
      </button>

      {isOpen ? (
        <div className="mt-2 flex flex-col gap-3">
          {error ? (
            <p role="alert" className="flex items-center gap-2 text-body-xs-regular text-danger-primary">
              <CircleAlert className="size-4 shrink-0" />
              The schedule could not be loaded. Try again.
            </p>
          ) : null}

          {sessions.map((session, index) => (
            <WorkshopSessionRow
              key={session.localId}
              session={session}
              index={index}
              total={sessions.length}
              assigneeIds={orderedAssigneeIds}
              disabled={disabled}
              timezone={timezone}
              onChange={(patch) => updateSession(session.localId, patch)}
              onRemove={() => setSessions((current) => current.filter((item) => item.localId !== session.localId))}
            />
          ))}

          {!sessions.length && !isLoading ? (
            <p className="text-body-xs-regular text-tertiary">
              No sessions yet. Add one to put this workshop on its trainers&apos; capacity.
            </p>
          ) : null}

          {disabled ? (
            <span className="text-11 text-placeholder">Times shown in {timezone}</span>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSessions((current) => [...current, newSession(orderedAssigneeIds)])}
              >
                <Plus className="size-3.5" /> Add session
              </Button>
              <Button
                variant="primary"
                size="sm"
                loading={saving || isLoading}
                disabled={!isSchedulable(sessions) || Boolean(error)}
                onClick={save}
              >
                Save schedule
              </Button>
              {data ? (
                <Button variant="secondary" size="sm" disabled={saving} onClick={remove}>
                  Remove all
                </Button>
              ) : null}
              <span className="ml-auto text-11 text-placeholder">Times shown in {timezone}</span>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
