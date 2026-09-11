/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { CapacityRequestError, CapacityService } from "@/services/capacity.service";
import { shiftWeek, startOfWeek } from "./capacity-format.utils";

const capacityService = new CapacityService();

/**
 * The trainer list and the week's capacity, which the ledger and the planner
 * both need.
 *
 * One `GET /capacity/` response feeds both surfaces: the ledger renders it as
 * per-trainer timelines, the planner runs `findWorkshopCandidates` over the same
 * intervals. Keeping the fetch in one place is what lets those become separate
 * routes without either duplicating the request or inventing a second source of
 * truth for the same numbers.
 *
 * The SWR keys are deliberately unchanged from the single-page version. Two
 * routes calling this hook compose an identical key and SWR dedupes them, so
 * this stays one request per week regardless of how many callers there are.
 *
 * The retry policy is load-bearing rather than decorative: the endpoint is
 * throttled per user *and* per workspace, and it answers a 429 with
 * `Retry-After`, which `CapacityRequestError` carries. Backing off by that
 * value, and capping the attempts, is why a rate-limited workspace recovers
 * instead of hammering.
 */
export function useCapacityData(workspaceSlug: string, enabled: boolean) {
  const [trainerCursor, setTrainerCursor] = useState<string | undefined>();
  const [cursorHistory, setCursorHistory] = useState<Array<string | undefined>>([]);
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const capacityRefreshRef = useRef<Promise<unknown> | null>(null);

  const weekEnd = useMemo(() => shiftWeek(weekStart, 1), [weekStart]);
  const rangeKey = `${weekStart.toISOString()}:${weekEnd.toISOString()}`;

  const {
    data: trainerPage,
    mutate: mutateTrainers,
    isLoading: trainersLoading,
  } = useSWR(enabled ? ["capacity-trainers", workspaceSlug, trainerCursor] : null, () =>
    capacityService.listTrainers(workspaceSlug, trainerCursor)
  );
  const trainers = trainerPage?.results;
  const trainerIds = trainers?.map((trainer) => trainer.user_id) ?? [];

  const {
    data: capacity,
    error: capacityError,
    mutate: mutateCapacity,
    isLoading: capacityLoading,
  } = useSWR(
    enabled && trainers ? ["capacity", workspaceSlug, rangeKey, trainerIds.join(",")] : null,
    () => capacityService.getCapacity(workspaceSlug, weekStart.toISOString(), weekEnd.toISOString(), trainerIds),
    {
      keepPreviousData: true,
      dedupingInterval: 5_000,
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      onErrorRetry: (error, _key, _config, revalidate, { retryCount }) => {
        if (retryCount >= 3) return;
        const retryAfter = error instanceof CapacityRequestError ? error.retryAfterSeconds : undefined;
        const delay = Math.min(60, Math.max(retryAfter ?? 0, 5 * 2 ** retryCount));
        globalThis.setTimeout(() => revalidate({ retryCount }), delay * 1000);
      },
    }
  );

  /**
   * Coalesce concurrent refreshes.
   *
   * Several unrelated actions invalidate this data -- opting in as a trainer,
   * saving a schedule, changing which calendars block time -- and a screen that
   * does two of them at once should still issue one request.
   */
  const refreshCapacity = useCallback(() => {
    if (capacityRefreshRef.current) return capacityRefreshRef.current;
    capacityRefreshRef.current = mutateCapacity().finally(() => {
      capacityRefreshRef.current = null;
    });
    return capacityRefreshRef.current;
  }, [mutateCapacity]);

  return {
    trainerPage,
    trainers,
    trainerIds,
    trainersLoading,
    mutateTrainers,
    capacity,
    capacityError,
    capacityLoading,
    refreshCapacity,
    weekStart,
    weekEnd,
    setWeekStart,
    trainerCursor,
    setTrainerCursor,
    cursorHistory,
    setCursorHistory,
  };
}
