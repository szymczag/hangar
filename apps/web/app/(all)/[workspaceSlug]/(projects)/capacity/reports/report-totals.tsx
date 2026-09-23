/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTrainingReportRow } from "@/services/capacity.service";
import { formatDateTime, formatHours } from "../shared/capacity-format.utils";
import { rowTotal } from "./report-totals.utils";

/**
 * What the workspace ran this month, and how much of it is trustworthy.
 *
 * A trainer whose calendar could not be read is left out of every total and
 * counted separately. Folding them in at zero would read as "ran nothing" to
 * somebody deciding who takes the next workshop, which is the opposite of what
 * the data says.
 */

export function ReportTotals({ rows, dataAsOf }: { rows: TTrainingReportRow[]; dataAsOf: string | null | undefined }) {
  const excluded = rows.filter((row) => !row.counts_towards_totals).length;
  const counted = rows.length - excluded;

  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
      <h2 className="text-body-sm-medium">
        {counted} trainer{counted === 1 ? "" : "s"} counted
      </h2>
      <span className="text-body-xs-regular text-secondary">
        {rowTotal(rows, "workshop_count")} workshops · {formatHours(rowTotal(rows, "delivery_minutes"))} delivered ·{" "}
        {formatHours(rowTotal(rows, "external_confirmed_minutes"))} external
      </span>
      {dataAsOf && <span className="text-body-xs-regular text-secondary">Data as of {formatDateTime(dataAsOf)}</span>}
      {excluded > 0 && <span className="text-body-xs-regular text-warning-primary">{excluded} not counted</span>}
    </div>
  );
}
