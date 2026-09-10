/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import useSWR from "swr";
import { CalendarClock } from "lucide-react";
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import { CapacityService, type TWorkshopSchedule } from "@/services/capacity.service";
import {
  toEditableSessions,
  WORKSHOP_SESSIONS_ANCHOR,
  workshopScheduleKey,
} from "@/components/issues/issue-detail-widgets/workshop-sessions";

const capacityService = new CapacityService();

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  issueTypeId: string | null;
  assigneeIds: string[];
};

/**
 * What the properties panel says about a workshop's sessions.
 *
 * The editor used to live here, and could not: seven stacked label/value rows
 * per session, in a panel `md:w-1/4` wide whose label gutter is a fixed 120px,
 * against `datetime-local` inputs the browser refuses to shrink. It now sits in
 * the work item body with the other widgets, and this is the summary that points
 * at it -- which is what every peer property does, a short truncatable value
 * with the real editing surface somewhere it fits.
 *
 * The SWR key is shared with the section, so this reads the same cache entry and
 * updates the moment a save revalidates it.
 */
export function WorkshopScheduleProperty({ workspaceSlug, projectId, issueId, issueTypeId, assigneeIds }: Props) {
  const { getTypeById } = useIssueTypes(workspaceSlug, projectId);
  const isWorkshop = getTypeById(issueTypeId)?.system_key === "workshop";

  const { data } = useSWR<TWorkshopSchedule | null>(
    isWorkshop ? workshopScheduleKey(workspaceSlug, projectId, issueId) : null,
    () => capacityService.getWorkshopSchedule(workspaceSlug, projectId, issueId)
  );

  if (!isWorkshop) return null;

  const sessions = toEditableSessions(data, assigneeIds).filter((session) => session.starts_at && session.ends_at);
  const starts = sessions.map((session) => new Date(session.starts_at).getTime());
  const ends = sessions.map((session) => new Date(session.ends_at).getTime());

  const span =
    starts.length > 0
      ? `${new Date(Math.min(...starts)).toLocaleDateString(undefined, {
          day: "numeric",
          month: "short",
        })} – ${new Date(Math.max(...ends)).toLocaleDateString(undefined, { day: "numeric", month: "short" })}`
      : null;

  const label = sessions.length
    ? `${sessions.length} ${sessions.length === 1 ? "session" : "sessions"}${span ? ` · ${span}` : ""}`
    : "Not scheduled";

  return (
    <SidebarPropertyListItem icon={CalendarClock} label="Workshop">
      <button
        type="button"
        title={label}
        onClick={() =>
          document.getElementById(WORKSHOP_SESSIONS_ANCHOR)?.scrollIntoView({ behavior: "smooth", block: "center" })
        }
        className="w-full truncate px-2 text-left text-body-xs-regular text-secondary hover:text-primary"
      >
        {label}
      </button>
    </SidebarPropertyListItem>
  );
}
