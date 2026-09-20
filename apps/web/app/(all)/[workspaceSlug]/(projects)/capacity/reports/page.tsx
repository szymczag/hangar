/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo } from "react";
import { useSearchParams } from "react-router";
import useSWR from "swr";
import { Download } from "lucide-react";
import { Button } from "@plane/propel/button";
import { Loader } from "@plane/ui";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import { CapacityService } from "@/services/capacity.service";
import type { Route } from "./+types/page";
import { formatMonthParam, parseMonthParam, shiftMonth } from "../shared/capacity-format.utils";
import { MonthStepper } from "../shared/month-stepper";
import { useViewerTimezone } from "../shared/viewer-timezone";
import { ReportNotices } from "./report-notices";
import { ReportTable } from "./report-table";
import { ReportTotals } from "./report-totals";

const capacityService = new CapacityService();

/**
 * How much training a team ran over a month.
 *
 * Answered from what the sweep has recorded, never from a live Google read --
 * which is the only reason a month is answerable at all. That makes freshness
 * part of the answer rather than a footnote: a trainer whose calendar has not
 * been read is marked and left out of the totals, because rendering them as a
 * zero would read as "ran nothing" to somebody deciding who takes the next
 * workshop.
 *
 * This component owns only the question -- which month, fetched how -- and hands
 * the answer to three pieces that each say one thing. What the report says about
 * its own trustworthiness lives in `ReportNotices` rather than between the
 * heading and the table, so the next such caveat has somewhere to go.
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

        <ReportNotices report={data} error={error} />

        {isLoading && !data ? (
          <Loader className="space-y-3">
            <Loader.Item height="40px" />
            <Loader.Item height="200px" />
          </Loader>
        ) : (
          <section aria-label="Training per trainer" className="rounded-xl border border-subtle bg-surface-1 p-5">
            <ReportTotals rows={rows} dataAsOf={data?.data_as_of} />
            <ReportTable rows={rows} />
          </section>
        )}
      </div>
    </div>
  );
}
