/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTrainingReportRow } from "@/services/capacity.service";

/**
 * Sum one column over the rows that may be trusted, and only those.
 *
 * A trainer whose calendar could not be read is left out of every total rather
 * than folded in at zero, which would read as "ran nothing" to somebody deciding
 * who takes the next workshop -- the opposite of what the data says.
 *
 * In a module of its own because a component file that also exports plain
 * functions cannot be hot-reloaded as a component.
 */
export function rowTotal(rows: TTrainingReportRow[], field: keyof TTrainingReportRow) {
  return rows.reduce((sum, row) => sum + (row.counts_towards_totals ? Number(row[field]) : 0), 0);
}
