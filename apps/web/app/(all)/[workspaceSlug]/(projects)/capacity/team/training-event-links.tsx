/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */
import { useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { CapacityService } from "@/services/capacity.service";
import type { TPlanIssue, TTrainerCapacity } from "@/services/capacity.service";
import { WorkshopPicker } from "../planner/workshop-picker";
import { dateTimeLabel } from "../planner/workshop-planner.utils";
import { errorMessage } from "../shared/capacity-format.utils";
import { useViewerTimezone } from "../shared/viewer-timezone";

const service = new CapacityService();
export function TrainingEventLinks({
  workspaceSlug,
  trainer,
  onChanged,
}: {
  workspaceSlug: string;
  trainer?: TTrainerCapacity;
  onChanged: () => Promise<unknown>;
}) {
  const [eventKey, setEventKey] = useState<string | null>(null);
  const [issue, setIssue] = useState<TPlanIssue | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const timeZone = useViewerTimezone();
  const { data: schedule, error: scheduleError } = useSWR(
    issue ? ["capacity-link-sessions", workspaceSlug, issue.project_id, issue.id] : null,
    () => service.getWorkshopSchedule(workspaceSlug, issue!.project_id, issue!.id)
  );
  const events = trainer?.training_workload?.events ?? [];
  const activeEvent = events.find((event) => event.key === eventKey);
  const save = async (key: string, sessionId?: string) => {
    setBusy(true);
    setError("");
    try {
      if (sessionId) await service.linkTrainingEvent(workspaceSlug, key, sessionId);
      else await service.unlinkTrainingEvent(workspaceSlug, key);
      setEventKey(null);
      setIssue(null);
      await onChanged();
    } catch (cause) {
      setError(errorMessage(cause, "Could not update the invitation link."));
    } finally {
      setBusy(false);
    }
  };
  if (!events.length) return null;
  return (
    <details className="rounded-xl border border-subtle bg-surface-1 p-5">
      <summary className="cursor-pointer text-body-sm-medium">Your recognized training invitations</summary>
      <p className="my-3 text-body-xs-regular text-secondary">
        Link an invitation to your existing Workshop session when they represent the same training. Linked invitations
        still block time, but their duration is counted only under Workshop sessions.
      </p>
      {error && (
        <p role="alert" className="text-danger-primary">
          {error}
        </p>
      )}
      <ul className="space-y-2">
        {events.map((event) => (
          <li
            key={event.key}
            className="flex flex-wrap items-center justify-between gap-2 border-b border-subtle py-2 text-body-xs-regular"
          >
            <span>
              {dateTimeLabel(event.start, undefined, timeZone)} · {event.status}
              {event.linked ? " · Linked to Workshop" : ""}
            </span>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy || trainer?.training_status !== "fresh"}
              onClick={() => (event.linked ? void save(event.key) : setEventKey(event.key))}
            >
              {event.linked ? "Unlink" : "Link to Workshop session"}
            </Button>
          </li>
        ))}
      </ul>
      {activeEvent && (
        <div className="mt-4 space-y-3">
          <WorkshopPicker workspaceSlug={workspaceSlug} value={issue} onChange={setIssue} />
          {scheduleError && <p role="alert">Could not load Workshop sessions.</p>}
          {schedule?.sessions
            .filter(
              (session) =>
                session.trainer_ids.includes(trainer!.trainer_id) &&
                session.starts_at < activeEvent.end &&
                session.ends_at > activeEvent.start
            )
            .map((session) => (
              <Button
                key={session.id}
                variant="secondary"
                size="sm"
                disabled={busy || !session.id}
                onClick={() => void save(activeEvent.key, session.id!)}
              >
                {dateTimeLabel(session.starts_at, undefined, timeZone)}
              </Button>
            ))}
          {issue && schedule === null && (
            <p className="text-body-xs-regular">This Workshop has no scheduled sessions yet.</p>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setEventKey(null);
              setIssue(null);
            }}
          >
            Cancel
          </Button>
        </div>
      )}
    </details>
  );
}
