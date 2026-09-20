/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTrainingReportRow, TTrainingSyncStatus } from "@/services/capacity.service";
import { formatHours } from "../shared/capacity-format.utils";

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

const COLUMNS = [
  "Trainer",
  "Workshops",
  "Sessions",
  "Delivered",
  "Preparation & travel",
  "External confirmed",
  "External pending",
];

/**
 * A row per trainer, saying plainly where a figure cannot be trusted.
 *
 * The external columns show a dash rather than zero for a trainer who is not
 * counted, because those two statements differ: a zero is a measurement, and a
 * dash is the absence of one.
 */
export function ReportTable({ rows }: { rows: TTrainingReportRow[] }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full text-left text-body-xs-regular">
        <thead className="text-secondary">
          <tr>
            {COLUMNS.map((label) => (
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
              <td colSpan={COLUMNS.length} className="px-3 py-6 text-center text-secondary">
                No trainers in this workspace yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
