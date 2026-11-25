/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useMemo, useState } from "react";
import { observer } from "mobx-react";
import { useSearchParams } from "react-router";
import useSWR from "swr";
import { Button } from "@makeplane/propel/components/button";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { Icon } from "@makeplane/propel/components/icon";
import { SelectField } from "@makeplane/propel/components/select-field";
import { CalendarOutline } from "@makeplane/propel/icons";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Loader } from "@plane/blocks/skeleton";
import { setToast } from "@plane/blocks/toast";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { useInstance } from "@/hooks/store/use-instance";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { CapacityService, type TPendingTrainingImport } from "@/services/capacity.service";
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
  workshops_not_enabled: "that project no longer offers Workshops",
};

/** One recognized training: its selection box, name, trainers, time, length and answer. */
function TrainingImportRow({
  row,
  selected,
  onToggle,
}: {
  row: TPendingTrainingImport;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <tr className="border-t border-subtle">
      <td className="px-3 py-3">
        <Checkbox
          aria-label={`Select ${row.title ?? "training"} with ${row.display_name}`}
          checked={selected}
          onCheckedChange={onToggle}
        />
      </td>
      <th scope="row" className="px-3 py-3 font-medium">
        {row.title ?? row.rule_label}
      </th>
      <td className="px-3 py-3">
        {/* Every trainer on the training, with whoever has not
            answered marked: importing takes all of them into one
            Workshop, so the row has to say who "all" is. */}
        {(row.trainers?.length
          ? row.trainers
          : [{ trainer_id: row.trainer_id, display_name: row.display_name, status: row.status }]
        ).map((trainer) => (
          <span key={trainer.trainer_id} className="block">
            {trainer.display_name}
            {trainer.status !== "confirmed" && <span className="ml-1 text-tertiary">· not answered</span>}
          </span>
        ))}
      </td>
      <td className="px-3 py-3">{formatDateTime(row.starts_at)}</td>
      <td className="px-3 py-3">{Math.round((row.minutes / 60) * 10) / 10}h</td>
      <td className="px-3 py-3">{row.status === "confirmed" ? "Accepted" : "Not answered yet"}</td>
    </tr>
  );
}

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
  const projectOptions = joinedProjectIds.map((id) => ({ value: id, label: getProjectById(id)?.name ?? id }));

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
        type: skipped ? "warning" : "success",
        title: `${result.created.length} workshop${result.created.length === 1 ? "" : "s"} created`,
        message: skipped
          ? `${skipped} skipped: ${[...new Set(result.skipped.map((row) => SKIP_COPY[row.reason] ?? row.reason))].join(", ")}.`
          : undefined,
      });
    } catch (reason: unknown) {
      setToast({
        type: "error",
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
              <div className="min-w-56">
                <SelectField<string>
                  label="Create workshops in"
                  size="lg"
                  placeholder="Choose a project"
                  options={projectOptions}
                  value={projectId || null}
                  onValueChange={(value) => setProjectId(value ?? "")}
                />
              </div>
              <Button
                variant="primary"
                size="lg"
                stretch="auto"
                loading={importing}
                disabled={!projectId || selected.size === 0}
                onClick={() => void runImport()}
                icon={<Icon icon={CalendarOutline} />}
                label={`Import ${selected.size > 0 ? selected.size : ""}`.trim()}
              />
              {rows.length > 0 && (
                <Button
                  variant="secondary"
                  size="lg"
                  stretch="auto"
                  onClick={() =>
                    setSelected((current) =>
                      current.size === rows.length ? new Set() : new Set(rows.map((row) => row.id))
                    )
                  }
                  label={selected.size === rows.length ? "Clear selection" : "Select all"}
                />
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
                    <TrainingImportRow
                      key={row.id}
                      row={row}
                      selected={selected.has(row.id)}
                      onToggle={() => toggle(row.id)}
                    />
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
