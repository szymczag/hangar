/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useSearchParams } from "react-router";
import useSWR from "swr";
import { CalendarPlus } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Loader } from "@plane/ui";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { CapacityService } from "@/services/capacity.service";
import type { Route } from "./+types/page";
import {
  errorMessage,
  formatDateTime,
  formatMonthParam,
  parseMonthParam,
  shiftMonth,
} from "../shared/capacity-format.utils";
import { MonthStepper } from "../shared/month-stepper";
import { useViewerTimezone } from "../shared/viewer-timezone";

const capacityService = new CapacityService();

/** What came back instead of a Workshop, in words rather than codes. */
const SKIP_COPY: Record<string, string> = {
  already_imported: "already imported",
  already_linked: "already linked to a session",
  no_longer_active: "no longer in the calendar",
  trainer_not_in_project: "the trainer cannot be assigned work in that project",
};

/**
 * Trainings that exist in the calendar but not yet as work items.
 *
 * The transitional surface. While the next months of training are planned in
 * the shared calendar, this is how they become Workshops that can carry a
 * checklist, a status and a client contact.
 *
 * Reviewed rather than automatic on purpose: a shared calendar carries plenty
 * that is not a workshop, and undoing a mistaken import means deleting work
 * items somebody may already have written on.
 */
const CapacityImportsPage = observer(function CapacityImportsPage({ params }: Route.ComponentProps) {
  const workspaceSlug = params.workspaceSlug;
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const { allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const { joinedProjectIds, getProjectById } = useProject();
  const timeZone = useViewerTimezone();
  const [searchParams, setSearchParams] = useSearchParams();

  const monthStart = useMemo(
    () => parseMonthParam(searchParams.get("month"), new Date(), timeZone),
    [searchParams, timeZone]
  );
  const monthEnd = useMemo(() => shiftMonth(monthStart, 1), [monthStart]);

  const [projectId, setProjectId] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);

  const setMonth = (next: (current: Date) => Date) =>
    setSearchParams(
      (previous) => {
        const current = parseMonthParam(previous.get("month"), new Date(), timeZone);
        const updated = new URLSearchParams(previous);
        updated.set("month", formatMonthParam(next(current)));
        return updated;
      },
      { replace: true, preventScrollReset: true }
    );

  const { data, error, isLoading, mutate } = useSWR(
    featureEnabled && isAdmin ? ["training-imports", workspaceSlug, monthStart.toISOString()] : null,
    () => capacityService.listPendingTrainingImports(workspaceSlug, monthStart.toISOString(), monthEnd.toISOString()),
    { revalidateOnFocus: false }
  );

  const rows = data?.results ?? [];

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const runImport = async () => {
    if (!projectId || selected.size === 0) return;
    setImporting(true);
    try {
      const result = await capacityService.importTrainings(workspaceSlug, projectId, [...selected]);
      setSelected(new Set());
      await mutate();
      const skipped = result.skipped.length;
      setToast({
        type: skipped ? TOAST_TYPE.WARNING : TOAST_TYPE.SUCCESS,
        title: `${result.created.length} workshop${result.created.length === 1 ? "" : "s"} created`,
        message: skipped
          ? `${skipped} skipped: ${[...new Set(result.skipped.map((row) => SKIP_COPY[row.reason] ?? row.reason))].join(", ")}.`
          : undefined,
      });
    } catch (reason: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Nothing was imported",
        message: errorMessage(reason, "Try again."),
      });
    } finally {
      setImporting(false);
    }
  };

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;
  if (!isAdmin) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <div className="h-full overflow-y-auto bg-surface-2">
      <div className="mx-auto flex max-w-[1440px] flex-col gap-5 p-4 md:p-6">
        <PageHead title="Import from calendar" />

        <div className="flex flex-wrap items-center gap-3">
          <div className="mr-auto">
            <h1 className="text-body-lg-medium">Import from calendar</h1>
            <p className="mt-1 text-body-xs-regular text-secondary">
              Recognized training that is not a work item yet. Importing creates a Workshop with its session and links
              the invitation, so the hours are never counted twice.
            </p>
          </div>
          <MonthStepper monthStart={monthStart} onChange={setMonth} />
        </div>

        {error && (
          <p role="alert" className="text-body-xs-regular text-danger-primary">
            {errorMessage(error, "The list could not be loaded.")}
          </p>
        )}

        {isLoading ? (
          <Loader className="space-y-3">
            <Loader.Item height="40px" />
            <Loader.Item height="200px" />
          </Loader>
        ) : (
          <section aria-label="Recognized training" className="rounded-xl border border-subtle bg-surface-1 p-5">
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-body-xs-regular">
                <span className="text-secondary">Create workshops in</span>
                <select
                  className="h-9 min-w-56 rounded-md border border-subtle bg-surface-2 px-2.5 text-body-sm-regular"
                  value={projectId}
                  onChange={(event) => setProjectId(event.target.value)}
                >
                  <option value="">Choose a project</option>
                  {joinedProjectIds.map((id) => (
                    <option key={id} value={id}>
                      {getProjectById(id)?.name}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                variant="primary"
                size="sm"
                loading={importing}
                disabled={!projectId || selected.size === 0}
                onClick={() => void runImport()}
              >
                <CalendarPlus className="mr-1 size-4" />
                Import {selected.size > 0 ? selected.size : ""}
              </Button>
              {rows.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() =>
                    setSelected((current) =>
                      current.size === rows.length ? new Set() : new Set(rows.map((row) => row.id))
                    )
                  }
                >
                  {selected.size === rows.length ? "Clear selection" : "Select all"}
                </Button>
              )}
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-body-xs-regular">
                <thead className="text-secondary">
                  <tr>
                    <th className="px-3 py-2 font-medium">
                      <span className="sr-only">Select</span>
                    </th>
                    {["Training", "Trainer", "When", "Length", "Response"].map((label) => (
                      <th key={label} className="px-3 py-2 font-medium">
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t border-subtle">
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          aria-label={`Select ${row.title ?? "training"} for ${row.display_name}`}
                          checked={selected.has(row.id)}
                          onChange={() => toggle(row.id)}
                        />
                      </td>
                      <th scope="row" className="px-3 py-3 font-medium">
                        {row.title ?? row.rule_label}
                      </th>
                      <td className="px-3 py-3">{row.display_name}</td>
                      <td className="px-3 py-3">{formatDateTime(row.starts_at)}</td>
                      <td className="px-3 py-3">{Math.round((row.minutes / 60) * 10) / 10}h</td>
                      <td className="px-3 py-3">{row.status === "confirmed" ? "Accepted" : "Not answered yet"}</td>
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-secondary">
                        Nothing to import this month. Recognized training that already has a work item is not listed.
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
});

export default CapacityImportsPage;
