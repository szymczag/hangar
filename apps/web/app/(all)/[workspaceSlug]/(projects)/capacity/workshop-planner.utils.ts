/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import type { TTrainerCapacity } from "@/services/capacity.service";
import { availableRanges } from "./capacity-timeline.utils";

export type TWorkshopCandidate = {
  trainerId: string;
  trainerName: string;
  timezone: string;
  availabilityStatus: string;
  workshopStartsAt: string;
  workshopEndsAt: string;
  blockedStartsAt: string;
  blockedEndsAt: string;
};

export function findWorkshopCandidates(
  trainers: TTrainerCapacity[],
  trainerIds: string[],
  windowStart: Date,
  windowEnd: Date,
  durationMinutes: number,
  preparationMinutes: number,
  travelBeforeMinutes: number,
  travelAfterMinutes: number
): TWorkshopCandidate[] {
  const beforeMinutes = preparationMinutes + travelBeforeMinutes;
  const totalMinutes = beforeMinutes + durationMinutes + travelAfterMinutes;
  if (durationMinutes <= 0 || totalMinutes <= 0 || windowStart >= windowEnd) return [];
  const selected = new Set(trainerIds);
  const candidates: TWorkshopCandidate[] = [];

  for (const trainer of trainers) {
    if (!selected.has(trainer.trainer_id)) continue;
    for (const range of availableRanges(trainer.intervals, windowStart, windowEnd)) {
      const blockedStart = new Date(range.start);
      const blockedEnd = new Date(blockedStart.getTime() + totalMinutes * 60_000);
      if (blockedEnd > new Date(range.end)) continue;
      const workshopStart = new Date(blockedStart.getTime() + beforeMinutes * 60_000);
      const workshopEnd = new Date(workshopStart.getTime() + durationMinutes * 60_000);
      candidates.push({
        trainerId: trainer.trainer_id,
        trainerName: trainer.display_name,
        timezone: trainer.timezone,
        availabilityStatus: trainer.availability_status,
        workshopStartsAt: workshopStart.toISOString(),
        workshopEndsAt: workshopEnd.toISOString(),
        blockedStartsAt: blockedStart.toISOString(),
        blockedEndsAt: blockedEnd.toISOString(),
      });
    }
  }
  const ordered: TWorkshopCandidate[] = [];
  for (const candidate of candidates) {
    const insertionIndex = ordered.findIndex((existing) =>
      candidate.workshopStartsAt === existing.workshopStartsAt
        ? candidate.trainerName.localeCompare(existing.trainerName) < 0
        : candidate.workshopStartsAt < existing.workshopStartsAt
    );
    if (insertionIndex === -1) ordered.push(candidate);
    else ordered.splice(insertionIndex, 0, candidate);
  }
  return ordered;
}
