/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TTrainerCapacity } from "@/services/capacity.service";

const duration = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`;

export function TeamWorkload({ trainers }: { trainers: TTrainerCapacity[] }) {
  if (!trainers.some((trainer) => trainer.workload)) return null;
  return (
    <section aria-label="Trainer workload" className="rounded-xl border border-subtle bg-surface-1 p-5">
      <h2 className="text-body-sm-medium">Trainer workload</h2>
      <p className="mt-1 text-body-xs-regular text-secondary">
        Selected week · Scheduled Workshop sessions, including work outside booking hours. Reservations are provisional.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-body-xs-regular">
          <thead className="text-secondary">
            <tr>
              {["Trainer", "Workshops", "Sessions", "Delivery", "Preparation & travel", "Reservations"].map((label) => (
                <th key={label} className="px-3 py-2 font-medium">
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trainers.map((trainer) => {
              const workload = trainer.workload;
              return (
                <tr key={trainer.trainer_id} className="border-t border-subtle">
                  <th scope="row" className="px-3 py-3 font-medium">
                    {trainer.display_name}
                  </th>
                  <td className="px-3 py-3">{workload?.workshop_count ?? "—"}</td>
                  <td className="px-3 py-3">{workload?.session_count ?? "—"}</td>
                  <td className="px-3 py-3">{workload ? duration(workload.delivery_minutes) : "—"}</td>
                  <td className="px-3 py-3">{workload ? duration(workload.buffer_minutes) : "—"}</td>
                  <td className="px-3 py-3">
                    {workload ? `${workload.hold_count} · ${duration(workload.hold_minutes)}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
