/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { useSearchParams } from "react-router";
import useSWR from "swr";
import { AlertTriangle, Download } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Loader } from "@plane/ui";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import { CapacityService } from "@/services/capacity.service";
import type { TTrainingReportRow, TTrainingSyncStatus } from "@/services/capacity.service";
import type { Route } from "./+types/page";
import {
  errorMessage,
  formatDate,
  formatDateTime,
  formatHours,
  formatMonthParam,
  parseMonthParam,
  shiftMonth,
} from "../shared/capacity-format.utils";
import { MonthStepper } from "../shared/month-stepper";
import { useViewerTimezone } from "../shared/viewer-timezone";

const capacityService = new CapacityService();

/** Why a row is not counted, in the words somebody planning staffing needs. */
const SYNC_COPY: Record<TTrainingSyncStatus, string> = {
  ok: "",
  stale: "Calendar data is out of date",
  never_synced: "Calendar has never been read",
  consent_missing: "Calendar access not granted",
  reauth_required: "Google connection needs renewing",
  not_connected: "No Google calendar connected",
  access_lost: "Lost access to the training calendar",
};

function rowTotal(rows: TTrainingReportRow[], field: keyof TTrainingReportRow) {
  return rows.reduce((sum, row) => sum + (row.counts_towards_totals ? Number(row[field]) : 0), 0);
}

/**
 * How much training a team ran over a month.
 *
 * Answered from what the sweep has recorded, never from a live Google read --
 * which is the only reason a month is answerable at all. That makes freshness
 * part of the answer rather than a footnote: a trainer whose calendar has not
 * been read is marked and left out of the totals, because rendering them as a
 * zero would read as "ran nothing" to somebody deciding who takes the next
 * workshop.
 */
export default function CapacityReportsPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const timeZone = useViewerTimezone();
  const [searchParams, setSearchParams] = useSearchParams();

  const monthStart = useMemo(
    () => parseMonthParam(searchParams.get("month"), new Date(), timeZone),
    [searchParams, timeZone]
  );
  const monthEnd = useMemo(() => shiftMonth(monthStart, 1), [monthStart]);

  const setMonth = (next: (current: Date) => Date) =>
    setSearchParams(
      (previous) => {
        const current = parseMonthParam(previous.get("month"), new Date(), timeZone);
        const updated = new URLSearchParams(previous);
        updated.set("month", formatMonthParam(next(current)));
        return updated;
      },
      // A stepper is not navigation: walking forward six months should not turn
      // Back into a month-by-month rewind of how you got here.
      { replace: true, preventScrollReset: true }
    );

  const { data, error, isLoading } = useSWR(
    featureEnabled ? ["training-report", workspaceSlug, monthStart.toISOString()] : null,
    () => capacityService.getTrainingReport(workspaceSlug, monthStart.toISOString(), monthEnd.toISOString()),
    { revalidateOnFocus: false, keepPreviousData: true }
  );

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;

  const rows = data?.trainers ?? [];
  const excluded = rows.filter((row) => !row.counts_towards_totals);
  const staleCalendars = data?.coverage.calendars.filter((calendar) => calendar.status !== "ok") ?? [];

  return (
    <div className="h-full overflow-y-auto bg-surface-2">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 p-4 md:p-6">
        <PageHead title="Training report" />

        <div className="flex flex-wrap items-center gap-3">
          <div className="mr-auto">
            <h1 className="text-body-lg-medium">Training report</h1>
            <p className="mt-1 text-body-xs-regular text-secondary">
              Delivered workshops and externally organized training, per trainer.
            </p>
          </div>
          <MonthStepper monthStart={monthStart} onChange={setMonth} />
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              window.location.assign(
                capacityService.trainingReportCsvUrl(workspaceSlug, monthStart.toISOString(), monthEnd.toISOString())
              )
            }
          >
            <Download className="mr-1 size-4" />
            Export CSV
          </Button>
        </div>

        {data && !data.coverage.requested_range_covered && (
          <p
            role="status"
            className="flex items-start gap-2 rounded-lg border border-subtle bg-surface-1 p-3 text-body-xs-regular text-secondary"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-primary" />
            This month falls outside the range currently collected
            {data.coverage.window_starts_at && data.coverage.window_ends_at
              ? ` (${formatDate(data.coverage.window_starts_at)} – ${formatDate(data.coverage.window_ends_at)})`
              : ""}
            , so externally organized training is not shown for it.
          </p>
        )}

        {staleCalendars.length > 0 && (
          <p
            role="status"
            className="flex items-start gap-2 rounded-lg border border-subtle bg-surface-1 p-3 text-body-xs-regular text-secondary"
          >
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-primary" />
            {staleCalendars.length === 1
              ? "One training calendar has not been read recently, so these figures may be out of date."
              : `${staleCalendars.length} training calendars have not been read recently, so these figures may be out of date.`}
          </p>
        )}

        {error && (
          <p role="alert" className="text-body-xs-regular text-danger-primary">
            {errorMessage(error, "The report could not be loaded.")}
          </p>
        )}

        {isLoading && !data ? (
          <Loader className="space-y-3">
            <Loader.Item height="40px" />
            <Loader.Item height="200px" />
          </Loader>
        ) : (
          <section aria-label="Training per trainer" className="rounded-xl border border-subtle bg-surface-1 p-5">
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <h2 className="text-body-sm-medium">
                {rows.length - excluded.length} trainer{rows.length - excluded.length === 1 ? "" : "s"} counted
              </h2>
              <span className="text-body-xs-regular text-secondary">
                {rowTotal(rows, "workshop_count")} workshops · {formatHours(rowTotal(rows, "delivery_minutes"))}{" "}
                delivered · {formatHours(rowTotal(rows, "external_confirmed_minutes"))} external
              </span>
              {data?.data_as_of && (
                <span className="text-body-xs-regular text-secondary">
                  Data as of {formatDateTime(data.data_as_of)}
                </span>
              )}
              {excluded.length > 0 && (
                <span className="text-body-xs-regular text-warning-primary">{excluded.length} not counted</span>
              )}
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-body-xs-regular">
                <thead className="text-secondary">
                  <tr>
                    {[
                      "Trainer",
                      "Workshops",
                      "Sessions",
                      "Delivered",
                      "Preparation & travel",
                      "External confirmed",
                      "External pending",
                    ].map((label) => (
                      <th key={label} className="px-3 py-2 font-medium">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.trainer_id} className="border-t border-subtle">
                      <th scope="row" className="px-3 py-3 font-medium">
                        {row.display_name}
                        {!row.counts_towards_totals && (
                          <span className="font-normal mt-0.5 block text-warning-primary">
                            {SYNC_COPY[row.sync_status] ?? "Not counted"}
                          </span>
                        )}
                      </th>
                      <td className="px-3 py-3">{row.workshop_count}</td>
                      <td className="px-3 py-3">{row.session_count}</td>
                      <td className="px-3 py-3">{formatHours(row.delivery_minutes)}</td>
                      <td className="px-3 py-3">{formatHours(row.buffer_minutes)}</td>
                      <td className="px-3 py-3">
                        {row.counts_towards_totals
                          ? `${row.external_confirmed_sessions} · ${formatHours(row.external_confirmed_minutes)}`
                          : "—"}
                      </td>
                      <td className="px-3 py-3">
                        {row.counts_towards_totals
                          ? `${row.external_pending_sessions} · ${formatHours(row.external_pending_minutes)}`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-3 py-6 text-center text-secondary">
                        No trainers in this workspace yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
