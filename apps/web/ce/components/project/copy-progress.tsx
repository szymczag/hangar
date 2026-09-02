/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { AlertTriangle, Check, Loader2 } from "lucide-react";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import { ProjectService } from "@/services/project/project.service";
import { cn } from "@plane/utils";

const projectService = new ProjectService();

// While one of these is the status there is more to come, so keep asking.
const ACTIVE = new Set(["queued", "processing"]);

type Props = {
  workspaceSlug: string;
  projectId: string;
};

/**
 * What a project's work item copy is doing, while it is doing it.
 *
 * The duplicate form returns as soon as the project exists, so somebody can be
 * looking at an empty project while its work items are still arriving. Without
 * this the copy looks broken rather than busy.
 *
 * Renders nothing for a project that was never copied, which is almost all of
 * them, and nothing once a clean copy has finished -- a permanent "this was
 * copied" banner is not information anyone needs twice.
 */
export const ProjectCopyProgress = ({ workspaceSlug, projectId }: Props) => {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useState(false);

  const { data } = useSWR(
    workspaceSlug && projectId ? `PROJECT_COPY_STATUS_${projectId}` : null,
    () => projectService.retrieveCopyStatus(workspaceSlug, projectId),
    {
      // Stops on its own once nothing is active, so a settled project costs one
      // request rather than one every three seconds forever.
      refreshInterval: (latest) => (ACTIVE.has(latest?.job?.status ?? "") ? 3000 : 0),
      revalidateOnFocus: true,
      shouldRetryOnError: false,
    }
  );

  const job = data?.job;
  if (!job || dismissed) return null;
  if (job.status === "completed" && !job.skipped.length) return null;
  if (job.status === "cancelled") return null;

  const running = ACTIVE.has(job.status);
  const failed = job.status === "failed";

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-start gap-3 border-b border-b-subtle px-4 py-2.5 sm:px-6",
        failed ? "bg-danger-subtle" : running ? "bg-accent-subtle" : "bg-warning-subtle"
      )}
    >
      {running ? (
        <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-secondary" aria-hidden="true" />
      ) : failed ? (
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-secondary" aria-hidden="true" />
      ) : (
        <Check className="mt-0.5 size-4 shrink-0 text-secondary" aria-hidden="true" />
      )}

      <div className="min-w-0 flex-1">
        <p className="text-13 leading-5 text-primary">
          {running
            ? t("project_copy_in_progress", { copied: job.copied, total: job.total })
            : failed
              ? t("project_copy_failed", { copied: job.copied, total: job.total })
              : t("project_copy_finished", { copied: job.copied })}
        </p>
        {/* What was deliberately left behind. Saying it once, here, is the only
            place anybody would find out that assignments were dropped. */}
        {!running && job.counts?.assignees_dropped ? (
          <p className="mt-0.5 text-11 leading-4 text-tertiary">
            {t("project_copy_assignees_dropped", { count: job.counts.assignees_dropped })}
          </p>
        ) : null}
      </div>

      {!running && (
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="shrink-0 text-11 font-medium text-accent-primary"
        >
          {t("dismiss")}
        </button>
      )}
    </div>
  );
};
