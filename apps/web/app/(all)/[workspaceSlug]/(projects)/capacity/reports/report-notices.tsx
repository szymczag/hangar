/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlertTriangle } from "lucide-react";
import type { TTrainingReport } from "@/services/capacity.service";
import { errorMessage, formatDate } from "../shared/capacity-format.utils";

/**
 * Everything the report says about itself before showing a number.
 *
 * Gathered here because freshness is part of this screen's answer rather than a
 * footnote to it: the figures come from a record, not a live read, so what the
 * record does not cover has to be said out loud. Keeping that reasoning in one
 * component is what stops the next such caveat being wedged between the table
 * and the heading.
 */

/** The shared shape of a caveat. Adding one is a line, not six lines of classes. */
function Notice({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="status"
      className="flex items-start gap-2 rounded-lg border border-subtle bg-surface-1 p-3 text-body-xs-regular text-secondary"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning-primary" />
      <span>{children}</span>
    </p>
  );
}

export function ReportNotices({ report, error }: { report: TTrainingReport | undefined; error: unknown }) {
  const coverage = report?.coverage;
  const staleCalendars = coverage?.calendars.filter((calendar) => calendar.status !== "ok") ?? [];
  const range =
    coverage?.window_starts_at && coverage.window_ends_at
      ? ` (${formatDate(coverage.window_starts_at)} – ${formatDate(coverage.window_ends_at)})`
      : "";

  return (
    <>
      {report && !coverage?.requested_range_covered && (
        <Notice>
          This month falls outside the range currently collected{range}, so externally organized training is not shown
          for it.
        </Notice>
      )}

      {staleCalendars.length > 0 && (
        <Notice>
          {staleCalendars.length === 1
            ? "One training calendar has not been read recently, so these figures may be out of date."
            : `${staleCalendars.length} training calendars have not been read recently, so these figures may be out of date.`}
        </Notice>
      )}

      {error ? (
        <p role="alert" className="text-body-xs-regular text-danger-primary">
          {errorMessage(error, "The report could not be loaded.")}
        </p>
      ) : null}
    </>
  );
}
