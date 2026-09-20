/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TCapacityInterval, TTrainerCapacity } from "@/services/capacity.service";
import { isOnlyTraining } from "../shared/capacity-timeline.utils";

const duration = (minutes: number) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`;

export function TeamWorkload({
  trainers,
  layers,
}: {
  trainers: TTrainerCapacity[];
  layers?: Set<TCapacityInterval["kind"]>;
}) {
  if (!trainers.some((trainer) => trainer.workload)) return null;
  // With only training on the timeline, the Hangar-side columns are noise:
  // the question being asked is about the calendar, not about delivery.
  const trainingOnly = layers ? isOnlyTraining(layers) : false;
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
              {(trainingOnly
                ? ["Trainer", "Google training", "Pending invitations"]
                : [
                    "Trainer",
                    "Workshops",
                    "Sessions",
                    "Delivery",
                    "Preparation & travel",
                    "Reservations",
                    "Google training",
                    "Pending invitations",
                  ]
              ).map((label) => (
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
                  {!trainingOnly && (
                    <>
                      <td className="px-3 py-3">{workload?.workshop_count ?? "—"}</td>
                      <td className="px-3 py-3">{workload?.session_count ?? "—"}</td>
                      <td className="px-3 py-3">{workload ? duration(workload.delivery_minutes) : "—"}</td>
                      <td className="px-3 py-3">{workload ? duration(workload.buffer_minutes) : "—"}</td>
                      <td className="px-3 py-3">
                        {workload ? `${workload.hold_count} · ${duration(workload.hold_minutes)}` : "—"}
                      </td>
                    </>
                  )}
                  <td className="px-3 py-3">
                    {trainer.training_status === "not_configured" || !trainer.training_workload
                      ? "—"
                      : `${trainer.training_workload.confirmed_sessions} · ${duration(trainer.training_workload.confirmed_minutes)}`}
                    {trainer.training_status && !["fresh", "not_configured"].includes(trainer.training_status) && (
                      <p className="text-danger-primary">
                        {trainer.training_status === "consent_required"
                          ? "Calendar access required"
                          : "Unverified calendar data"}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    {trainer.training_workload
                      ? `${trainer.training_workload.pending_sessions} · ${duration(trainer.training_workload.pending_minutes)}`
                      : "—"}
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
