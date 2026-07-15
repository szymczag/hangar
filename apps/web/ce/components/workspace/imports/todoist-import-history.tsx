/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import useSWR from "swr";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { importService } from "@/plane-web/services/import.service";
import type { TImportJob } from "@/plane-web/types/import";

const ACTIVE_STATUSES = new Set(["preparing", "queued", "processing", "cancelling"]);
const CANCELLABLE_STATUSES = new Set(["preparing", "queued", "processing"]);
const REPORT_STATUSES = new Set(["completed", "completed_with_errors", "failed", "cancelled"]);

type Props = {
  workspaceSlug: string;
  errorMessage: (error: unknown) => string;
  refreshToken: number;
  onRetry: (job: TImportJob) => void;
};

export function TodoistImportHistory({ workspaceSlug, errorMessage, refreshToken, onRetry }: Props) {
  const { t } = useTranslation();
  const statusLabels: Record<TImportJob["status"], string> = {
    preparing: t("workspace_settings.settings.todoist_import.history.status.preparing"),
    queued: t("workspace_settings.settings.todoist_import.history.status.queued"),
    processing: t("workspace_settings.settings.todoist_import.history.status.processing"),
    cancelling: t("workspace_settings.settings.todoist_import.history.status.cancelling"),
    completed: t("workspace_settings.settings.todoist_import.history.status.completed"),
    completed_with_errors: t("workspace_settings.settings.todoist_import.history.status.completed_with_errors"),
    failed: t("workspace_settings.settings.todoist_import.history.status.failed"),
    cancelled: t("workspace_settings.settings.todoist_import.history.status.cancelled"),
  };
  const [cursor, setCursor] = useState("20:0:0");
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const { data, error, isLoading, mutate } = useSWR(
    workspaceSlug ? ["todoist-imports", workspaceSlug, cursor, refreshToken] : null,
    () => importService.list(workspaceSlug, cursor),
    {
      refreshInterval: (jobs) => (jobs?.results.some((job) => ACTIVE_STATUSES.has(job.status)) ? 3000 : 0),
    }
  );

  useEffect(() => setCursor("20:0:0"), [workspaceSlug]);

  const cancel = async (jobId: string) => {
    setCancellingJobId(jobId);
    try {
      await importService.cancel(workspaceSlug, jobId);
      await mutate();
    } catch (cancelError) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("workspace_settings.settings.todoist_import.history.cancel_error"),
        message: errorMessage(cancelError),
      });
    } finally {
      setCancellingJobId(null);
    }
  };

  return (
    <section>
      <div className="mb-3">
        <h3 className="text-h5-medium text-primary">{t("workspace_settings.settings.todoist_import.history.title")}</h3>
        <p className="mt-1 text-body-sm-regular text-secondary">
          {t("workspace_settings.settings.todoist_import.history.description")}
        </p>
      </div>
      <div className="overflow-hidden rounded-xl border border-subtle bg-layer-1">
        {isLoading ? (
          <div className="flex items-center gap-2 p-5 text-body-sm-regular text-secondary">
            <Loader2 className="size-4 animate-spin" />
            {t("workspace_settings.settings.todoist_import.history.loading")}
          </div>
        ) : error ? (
          <div className="p-5 text-body-sm-regular text-danger-primary">
            {t("workspace_settings.settings.todoist_import.history.error")}
          </div>
        ) : !data?.results.length ? (
          <div className="p-6 text-body-sm-regular text-secondary">
            {t("workspace_settings.settings.todoist_import.history.empty")}
          </div>
        ) : (
          <div className="divide-y divide-subtle">
            {data.results.map((job) => {
              const statusLabel =
                (statusLabels as Record<string, string>)[job.status] ??
                t("workspace_settings.settings.todoist_import.history.status.unknown");
              const importedTasks = job.stats.imported_tasks ?? 0;
              const reusedTasks = job.stats.reused_tasks ?? 0;
              return (
                <div key={job.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-start gap-3">
                    {job.status === "completed" ? (
                      <CheckCircle2 className="mt-0.5 size-4 text-success-primary" />
                    ) : ACTIVE_STATUSES.has(job.status) ? (
                      <Loader2 className="mt-0.5 size-4 animate-spin text-accent-primary" />
                    ) : (
                      <AlertTriangle className="mt-0.5 size-4 text-warning-primary" />
                    )}
                    <div className="min-w-0">
                      <p className="truncate text-body-sm-medium text-primary">{job.project_detail.name}</p>
                      <p className="mt-0.5 text-body-xs-regular text-secondary">
                        {statusLabel} · {importedTasks + reusedTasks}{" "}
                        {t("workspace_settings.settings.todoist_import.history.of")} {job.stats.planned_tasks ?? 0}{" "}
                        {t("workspace_settings.settings.todoist_import.tasks").toLocaleLowerCase()}
                      </p>
                      {reusedTasks > 0 && (
                        <p className="mt-0.5 text-body-xs-regular text-secondary">
                          {importedTasks} {t("workspace_settings.settings.todoist_import.history.imported")} ·{" "}
                          {reusedTasks} {t("workspace_settings.settings.todoist_import.history.reused")}
                        </p>
                      )}
                      {job.retry_of && (
                        <p className="mt-0.5 text-body-xs-regular text-secondary">
                          {t("workspace_settings.settings.todoist_import.history.retry_of")} {job.retry_of.slice(0, 8)}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {job.status === "failed" && (
                      <Button variant="secondary" size="sm" onClick={() => onRetry(job)}>
                        {t("workspace_settings.settings.todoist_import.history.retry")}
                      </Button>
                    )}
                    {CANCELLABLE_STATUSES.has(job.status) && (
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={cancellingJobId === job.id || Boolean(job.cancel_requested_at)}
                        onClick={() => void cancel(job.id)}
                      >
                        {job.cancel_requested_at
                          ? t("workspace_settings.settings.todoist_import.history.cancellation_requested")
                          : t("workspace_settings.settings.todoist_import.history.cancel")}
                      </Button>
                    )}
                    {REPORT_STATUSES.has(job.status) && (
                      <a
                        className="text-body-xs-medium text-accent-primary hover:underline"
                        href={importService.reportUrl(workspaceSlug, job.id)}
                      >
                        {t("workspace_settings.settings.todoist_import.history.download_report")}
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      {data && (data.prev_page_results || data.next_page_results) && (
        <div className="mt-3 flex justify-end gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={!data.prev_page_results}
            onClick={() => data.prev_cursor && setCursor(data.prev_cursor)}
          >
            {t("workspace_settings.settings.todoist_import.history.newer")}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!data.next_page_results}
            onClick={() => data.next_cursor && setCursor(data.next_cursor)}
          >
            {t("workspace_settings.settings.todoist_import.history.older")}
          </Button>
        </div>
      )}
    </section>
  );
}
