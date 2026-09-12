/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR, { mutate } from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CalendarCheck, CalendarSearch, Clock3, Save, ShieldCheck, Trash2, Users } from "lucide-react";
import { errorMessage, formatMinutes, startOfWeek } from "../shared/capacity-format.utils";
import {
  CapacityService,
  type TPlanIssue,
  type TTrainerCapacity,
  type TWorkshopPlanDraft,
  type TWorkshopPlanDraftInput,
  type TWorkshopPlanHold,
} from "@/services/capacity.service";
import { WorkshopPicker, workshopLabel } from "./workshop-picker";
import {
  dateTimeLabel,
  dayLabel,
  findFirstAvailable,
  findWorkshopCandidates,
  groupByDay,
  MAX_SLOTS_PER_TRAINER_PER_DAY,
  noWorkshopFitReason,
  nextBookingMinute,
  workshopAvailability,
  sameLocalDay,
  timeLabel,
  type TFirstAvailable,
  type TStartWindow,
  type TWorkshopCandidate,
} from "./workshop-planner.utils";

const capacityService = new CapacityService();

/**
 * What makes this plan a different plan.
 *
 * Deliberately not the week on screen. The window used to be part of a draft,
 * so stepping to the next week marked the plan unsaved -- which, with a hold
 * open, meant a save the server refuses and a candidate list that will not let
 * you act. A plan is what has to happen and who could deliver it; when you are
 * looking is the planner's `?week=`, not the plan's.
 */
export const planSignature = (plan: TWorkshopPlanDraftInput) =>
  JSON.stringify({
    ...plan,
    // ES2022 is the web app's current target; the copied array keeps sort() mutation local.
    // oxlint-disable-next-line unicorn/no-array-sort
    trainer_ids: [...plan.trainer_ids].sort(),
  });

function NumberField({
  label,
  value,
  onChange,
  disabled = false,
  min = 0,
  max = 1440,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
  min?: number;
  max?: number;
}) {
  return (
    <label className="text-body-xs-medium text-secondary">
      {label}
      <div className="relative mt-1">
        <input
          type="number"
          min={min}
          max={max}
          step={15}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(Math.max(0, Number(event.target.value)))}
          className="h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 pr-11 text-body-sm-regular text-primary disabled:cursor-not-allowed disabled:opacity-60"
        />
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-11 text-placeholder">
          min
        </span>
      </div>
    </label>
  );
}

export function WorkshopPlanner({
  workspaceSlug,
  trainers,
  weekStart,
  weekEnd,
  onViewWeek,
  capacityState = "ready",
  capacityError,
  onRetry,
}: {
  workspaceSlug: string;
  trainers: TTrainerCapacity[];
  weekStart: Date;
  weekEnd: Date;
  onViewWeek: (start: Date) => void;
  capacityState?: "ready" | "loading" | "error";
  capacityError?: string;
  onRetry?: () => void;
}) {
  const { data: draftPage, mutate: mutateDrafts } = useSWR(["workshop-plan-drafts", workspaceSlug], () =>
    capacityService.listWorkshopPlanDrafts(workspaceSlug)
  );
  const [draftId, setDraftId] = useState<string | null>(null);
  const [revision, setRevision] = useState<number | null>(null);
  const [title, setTitle] = useState("");
  /**
   * The Workshop work item this plan is for.
   *
   * Held alongside `title` rather than instead of it: the title is still what
   * names a saved draft in the picker above, and an exploratory plan has one
   * without having a work item. Attaching a work item adopts its name, so the
   * two do not drift for the common case.
   */
  const [issue, setIssue] = useState<TPlanIssue | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [durationMinutes, setDurationMinutes] = useState(240);
  const [preparationMinutes, setPreparationMinutes] = useState(30);
  const [travelBeforeMinutes, setTravelBeforeMinutes] = useState(60);
  const [travelAfterMinutes, setTravelAfterMinutes] = useState(60);
  const [trainerIds, setTrainerIds] = useState(() => trainers.map((trainer) => trainer.trainer_id));
  /**
   * Which half of the day to look in.
   *
   * Not part of the draft: it narrows the same plan rather than describing a
   * different one, the way the week does. Saving it would put "I asked about
   * afternoons once" into the plan for good.
   */
  const [startWindow, setStartWindow] = useState<TStartWindow>("any");
  const [saving, setSaving] = useState(false);
  const [hold, setHold] = useState<TWorkshopPlanHold | null>(null);
  const [savedSignature, setSavedSignature] = useState<string | null>(null);
  const [now, setNow] = useState(() => new Date());
  const searchController = useRef<AbortController | null>(null);
  const [searchState, setSearch] = useState<
    | { state: "idle" }
    | { state: "running"; from: Date; key: string }
    | { state: "done"; result: TFirstAvailable; forTrainer: string | null; key: string }
  >({ state: "idle" });

  const spec = useMemo(
    () => ({
      trainerIds,
      durationMinutes,
      preparationMinutes,
      travelBeforeMinutes,
      travelAfterMinutes,
      startWindow,
      notBefore: nextBookingMinute(now),
    }),
    [trainerIds, durationMinutes, preparationMinutes, travelBeforeMinutes, travelAfterMinutes, startWindow, now]
  );
  // A result belongs to the requirements that produced it, including the viewed week.
  const searchKey = JSON.stringify({
    workspaceSlug,
    draftId,
    week: weekStart.toISOString(),
    ...spec,
    notBefore: undefined,
  });
  const search =
    searchState.state !== "idle" && searchState.key === searchKey ? searchState : { state: "idle" as const };
  useEffect(() => () => searchController.current?.abort(), [searchKey]);
  useEffect(() => {
    const timer = globalThis.setInterval(() => setNow(new Date()), 60_000);
    return () => globalThis.clearInterval(timer);
  }, []);

  const refreshPlanningData = () =>
    Promise.allSettled([
      mutateDrafts(),
      mutate((key) => Array.isArray(key) && key[0] === "capacity" && key[1] === workspaceSlug),
    ]);
  useEffect(() => {
    if (!hold) return;
    const timer = globalThis.setTimeout(
      () => {
        setHold(null);
        setNow(new Date());
        void Promise.allSettled([
          mutateDrafts(),
          mutate((key) => Array.isArray(key) && key[0] === "capacity" && key[1] === workspaceSlug),
        ]);
      },
      Math.max(0, new Date(hold.expires_at).getTime() - Date.now())
    );
    return () => globalThis.clearTimeout(timer);
  }, [hold, mutateDrafts, workspaceSlug]);

  /**
   * Look past the week on screen for the next time this fits.
   *
   * `only` restricts the search to one trainer, which is the same question with
   * a smaller eligible set -- "when could she do it?" rather than "when could
   * anybody?". Passing null asks about everyone currently ticked.
   */
  const findNext = async (only: string | null) => {
    const ids = only ? [only] : trainerIds;
    if (!ids.length) return;
    searchController.current?.abort();
    const controller = new AbortController();
    searchController.current = controller;
    const notBefore = nextBookingMinute(new Date());
    const from = new Date(Math.max(weekStart.getTime(), startOfWeek(notBefore).getTime()));
    setSearch({ state: "running", from, key: searchKey });
    try {
      const result = await findFirstAvailable(
        from,
        { ...spec, trainerIds: ids, notBefore },
        async (windowStart, windowEnd) => {
          const response = await capacityService.getCapacity(
            workspaceSlug,
            windowStart.toISOString(),
            windowEnd.toISOString(),
            ids,
            controller.signal
          );
          return response.trainers;
        },
        {
          signal: controller.signal,
          onProgress: (windowStart) => setSearch({ state: "running", from: windowStart, key: searchKey }),
        }
      );
      if (!controller.signal.aborted) setSearch({ state: "done", result, forTrainer: only, key: searchKey });
    } catch (error: unknown) {
      if (controller.signal.aborted) return;
      setSearch({ state: "idle" });
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Search could not finish",
        message: errorMessage(error, "Try again shortly. The full date range has not been checked."),
      });
    }
  };

  const candidates = useMemo(
    () => (capacityState === "ready" ? findWorkshopCandidates(trainers, weekStart, weekEnd, spec) : []),
    [capacityState, trainers, weekStart, weekEnd, spec]
  );
  const availability = useMemo(
    () => workshopAvailability(trainers, weekStart, weekEnd, spec),
    [trainers, weekStart, weekEnd, spec]
  );
  const candidateDays = useMemo(() => groupByDay(candidates), [candidates]);

  /**
   * A held plan is frozen, because the server freezes it: `PUT /capacity/plans/`
   * answers 409 while a hold is active, so that the block someone is holding
   * still means what it said when they took it. The form reflects that rather
   * than letting you type into fields whose save is guaranteed to be refused.
   */
  const isHeld = Boolean(hold);
  const busy = saving || scheduling;
  const formLocked = isHeld || busy;
  const validDuration = Number.isInteger(durationMinutes) && durationMinutes >= 15 && durationMinutes <= 10080;
  const validBuffers = [preparationMinutes, travelBeforeMinutes, travelAfterMinutes].every(
    (value) => Number.isInteger(value) && value >= 0 && value <= 1440
  );
  const validPlan = validDuration && validBuffers;

  const payload = (): TWorkshopPlanDraftInput => ({
    title: title.trim(),
    duration_minutes: durationMinutes,
    preparation_minutes: preparationMinutes,
    travel_before_minutes: travelBeforeMinutes,
    travel_after_minutes: travelAfterMinutes,
    trainer_ids: trainerIds,
    issue_id: issue?.id ?? null,
  });
  const planNeedsSaving = savedSignature !== planSignature(payload());

  const loadDraft = (draft: TWorkshopPlanDraft) => {
    searchController.current?.abort();
    setSearch({ state: "idle" });
    setDraftId(draft.id);
    setRevision(draft.revision);
    setTitle(draft.title);
    setIssue(draft.issue);
    setDurationMinutes(draft.duration_minutes);
    setPreparationMinutes(draft.preparation_minutes);
    setTravelBeforeMinutes(draft.travel_before_minutes);
    setTravelAfterMinutes(draft.travel_after_minutes);
    setTrainerIds(draft.trainer_ids.filter((id) => trainers.some((trainer) => trainer.trainer_id === id)));
    setHold(draft.hold);
    setSavedSignature(
      planSignature({
        title: draft.title,
        duration_minutes: draft.duration_minutes,
        preparation_minutes: draft.preparation_minutes,
        travel_before_minutes: draft.travel_before_minutes,
        travel_after_minutes: draft.travel_after_minutes,
        trainer_ids: draft.trainer_ids.filter((id) => trainers.some((trainer) => trainer.trainer_id === id)),
        issue_id: draft.issue?.id ?? null,
      })
    );
  };

  const reset = () => {
    searchController.current?.abort();
    setSearch({ state: "idle" });
    setStartWindow("any");
    setDraftId(null);
    setRevision(null);
    setTitle("");
    setIssue(null);
    setDurationMinutes(240);
    setPreparationMinutes(30);
    setTravelBeforeMinutes(60);
    setTravelAfterMinutes(60);
    setTrainerIds(trainers.map((trainer) => trainer.trainer_id));
    setHold(null);
    setSavedSignature(null);
  };

  const persistDraft = async (fallbackTitle?: string) => {
    const input = { ...payload(), title: title.trim() || fallbackTitle || "Workshop plan" };
    const saved =
      draftId && revision !== null
        ? await capacityService.updateWorkshopPlanDraft(workspaceSlug, draftId, revision, input)
        : await capacityService.createWorkshopPlanDraft(workspaceSlug, input);
    loadDraft(saved);
    return saved;
  };

  const saveDraft = async () => {
    if (!trainerIds.length || !validPlan || formLocked) return;
    setSaving(true);
    try {
      await persistDraft();
      await mutateDrafts();
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Plan saved", message: "Choose a time to hold it for 72 hours." });
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Plan not saved", message: errorMessage(error, "Try again.") });
    } finally {
      setSaving(false);
    }
  };

  const deleteDraft = async () => {
    if (!draftId) return;
    setSaving(true);
    try {
      await capacityService.deleteWorkshopPlanDraft(workspaceSlug, draftId);
      reset();
      await refreshPlanningData();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Plan not deleted", message: errorMessage(error, "Try again.") });
    } finally {
      setSaving(false);
    }
  };

  const holdCandidate = async (candidate: TWorkshopCandidate) => {
    if (formLocked || !validPlan || capacityState !== "ready") return;
    if (new Date(candidate.blockedStartsAt).getTime() <= Date.now()) {
      setNow(new Date());
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Choose a later time",
        message: "Preparation or travel for this slot has already started.",
      });
      return;
    }
    setSaving(true);
    try {
      // Use the returned revision, not React state from before this save.
      const saved =
        planNeedsSaving || !draftId || revision === null
          ? await persistDraft(`Workshop · ${dateTimeLabel(candidate.workshopStartsAt)}`)
          : { id: draftId, revision };
      const result = await capacityService.holdWorkshopPlan(
        workspaceSlug,
        saved.id,
        saved.revision,
        candidate.trainerId,
        candidate.workshopStartsAt
      );
      setHold(result.hold);
      setRevision(result.revision);
      setSearch({ state: "idle" });
      searchController.current?.abort();
      await refreshPlanningData();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Time held for 72 hours",
        message: "Your plan is saved. Schedule this workshop, or start another plan while this time stays held.",
      });
    } catch (error: unknown) {
      await refreshPlanningData();
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Time could not be held",
        message: errorMessage(error, "Refresh availability and choose another time."),
      });
    } finally {
      setSaving(false);
    }
  };

  /**
   * Spend the hold. The server appends the session, assigns the trainer and
   * marks the hold scheduled in one transaction, so there is nothing to undo
   * here if it refuses -- and on a refusal the hold is deliberately left alone.
   */
  const scheduleHold = async () => {
    if (!draftId || revision === null || !issue) return;
    setScheduling(true);
    try {
      const result = await capacityService.scheduleWorkshopPlan(workspaceSlug, draftId, revision);
      setRevision(result.revision);
      setHold(null);
      await refreshPlanningData();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workshop scheduled",
        message: `${hold?.trainer_name ?? "The trainer"} is booked on ${workshopLabel(result.issue)}. Choose another time to add a session, or start a new plan.`,
      });
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Not scheduled",
        message: errorMessage(error, "The hold is untouched. Refresh capacity and try again."),
      });
    } finally {
      setScheduling(false);
    }
  };

  const releaseHold = async () => {
    if (!draftId) return;
    setSaving(true);
    try {
      const result = await capacityService.releaseWorkshopPlanHold(workspaceSlug, draftId);
      setHold(null);
      setRevision(result.revision);
      await refreshPlanningData();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Hold not released", message: errorMessage(error, "Try again.") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="overflow-hidden rounded-xl border border-subtle bg-surface-1">
      <div className="flex flex-col gap-2 border-b border-subtle px-5 py-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-2 flex items-center gap-2 text-11 font-semibold tracking-[0.16em] text-placeholder uppercase">
            <CalendarSearch className="size-3.5" /> Workshop planner
          </div>
          <h2 className="text-lg font-semibold text-primary">What needs to happen, who can deliver it, and when?</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">
            The entire trainer block—preparation, outbound travel, delivery, and return travel—must fit in live
            availability.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            aria-label="Saved planning drafts"
            value={draftId ?? ""}
            onChange={(event) => {
              const draft = draftPage?.results.find((item) => item.id === event.target.value);
              if (draft) loadDraft(draft);
              else reset();
            }}
            disabled={busy}
            className="h-8 rounded-md border border-subtle bg-surface-2 px-2 text-body-xs-regular disabled:cursor-not-allowed disabled:opacity-60"
          >
            <option value="">New plan</option>
            {draftPage?.results.map((draft) => (
              <option key={draft.id} value={draft.id}>
                {draft.title}
                {draft.hold ? " · Time held" : ""}
              </option>
            ))}
          </select>
          <Button
            variant="primary"
            size="sm"
            loading={saving}
            disabled={formLocked || !trainerIds.length || !validPlan}
            title={isHeld ? "Release the hold before changing this plan" : undefined}
            onClick={saveDraft}
          >
            <Save className="size-3.5" /> Save plan
          </Button>
          <Button variant="secondary" size="sm" disabled={busy} onClick={reset}>
            Start another plan
          </Button>
          {draftId ? (
            <Button variant="secondary" size="sm" disabled={busy} onClick={deleteDraft}>
              <Trash2 className="size-3.5" /> Delete
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-0 xl:grid-cols-[380px_1fr]">
        <div className="space-y-5 border-b border-subtle p-5 xl:border-r xl:border-b-0">
          <WorkshopPicker
            workspaceSlug={workspaceSlug}
            value={issue}
            disabled={formLocked}
            onChange={(next) => {
              setIssue(next);
              // Adopt the work item's name unless the coordinator has already
              // named the draft something of their own.
              if (next && (!title.trim() || title === issue?.name)) setTitle(next.name);
            }}
          />
          <label className="block text-body-xs-medium text-secondary">
            Plan name (optional)
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. NetSec workshop"
              maxLength={255}
              disabled={formLocked}
              className="mt-1 h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-body-sm-regular text-primary disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <NumberField
              label="Workshop duration"
              value={durationMinutes}
              onChange={setDurationMinutes}
              disabled={formLocked}
              min={15}
              max={10080}
            />
            <NumberField
              label="Preparation"
              value={preparationMinutes}
              onChange={setPreparationMinutes}
              disabled={formLocked}
            />
            <NumberField
              label="Travel before"
              value={travelBeforeMinutes}
              onChange={setTravelBeforeMinutes}
              disabled={formLocked}
            />
            <NumberField
              label="Travel back"
              value={travelAfterMinutes}
              onChange={setTravelAfterMinutes}
              disabled={formLocked}
            />
          </div>
          <div
            className="rounded-lg border border-accent-subtle bg-layer-2 p-3"
            aria-label="Time needed for this plan"
            aria-live="polite"
          >
            <p className="text-body-xs-medium text-secondary">One continuous booking</p>
            <p className="text-xl mt-1 font-semibold text-primary tabular-nums">
              {formatMinutes(availability.requiredMinutes)}
            </p>
            <p className="mt-1 text-body-xs-regular text-secondary">
              {formatMinutes(durationMinutes)} workshop + {formatMinutes(availability.bufferMinutes)} preparation and
              travel. All of it must fit inside the trainer’s booking hours.
            </p>
            {!validDuration ? (
              <p role="alert" className="mt-2 text-11 text-danger-primary">
                Workshop duration must be a whole number from 15 to 10080 minutes.
              </p>
            ) : null}
            {!validBuffers ? (
              <p role="alert" className="mt-2 text-11 text-danger-primary">
                Each buffer must be a whole number from 0 to 1440 minutes.
              </p>
            ) : null}
          </div>
          <fieldset>
            <legend className="text-body-xs-medium text-secondary">Start</legend>
            <div className="mt-1 flex rounded-md border border-subtle bg-surface-2 p-0.5">
              {(
                [
                  ["any", "Any time"],
                  ["morning", "Morning"],
                  ["afternoon", "Afternoon"],
                ] as Array<[TStartWindow, string]>
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={startWindow === value}
                  disabled={busy}
                  onClick={() => setStartWindow(value)}
                  className={`flex-1 rounded px-2 py-1 text-11 ${
                    startWindow === value ? "shadow-xs bg-surface-1 font-medium text-primary" : "text-secondary"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="flex items-center gap-2 text-body-xs-medium text-secondary">
              <Users className="size-3.5" /> Eligible trainers
            </legend>
            <div className="mt-2 space-y-1.5">
              {trainers.map((trainer) => (
                <label
                  key={trainer.trainer_id}
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-body-xs-regular ${
                    isHeld ? "opacity-60" : "cursor-pointer hover:bg-surface-2"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={trainerIds.includes(trainer.trainer_id)}
                    disabled={formLocked}
                    onChange={() =>
                      setTrainerIds((current) =>
                        current.includes(trainer.trainer_id)
                          ? current.filter((id) => id !== trainer.trainer_id)
                          : [...current, trainer.trainer_id]
                      )
                    }
                  />
                  <span className="min-w-0 flex-1 truncate text-primary">{trainer.display_name}</span>
                  <span className="text-11 text-placeholder">{trainer.timezone}</span>
                  <button
                    type="button"
                    title={`Find the first time ${trainer.display_name} could do this`}
                    disabled={busy || isHeld || !validPlan || search.state === "running"}
                    onClick={(event) => {
                      // The row is a label, so a click here would otherwise toggle
                      // the checkbox it wraps.
                      event.preventDefault();
                      void findNext(trainer.trainer_id);
                    }}
                    className="shrink-0 rounded px-1.5 py-0.5 text-11 text-accent-primary hover:bg-surface-2 disabled:opacity-50"
                  >
                    When?
                  </button>
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        <div className="p-5">
          {hold ? (
            <div className="bg-accent-secondary/10 mb-5 flex flex-col gap-3 rounded-lg border border-accent-subtle p-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <div className="flex gap-3">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-accent-primary" />
                <div>
                  <h3 className="text-body-sm-medium text-primary">Time held for {hold.trainer_name}</h3>
                  <p className="mt-1 text-body-xs-regular text-secondary">
                    {dateTimeLabel(hold.workshop_starts_at)} –{" "}
                    {new Date(hold.workshop_ends_at).toLocaleTimeString(undefined, { timeStyle: "short" })}. Expires{" "}
                    {dateTimeLabel(hold.expires_at)}. This is a temporary reservation, not a scheduled workshop.
                  </p>
                  <p className="mt-1 text-11 text-placeholder">
                    {issue
                      ? `Schedule this session on ${workshopLabel(issue)}, or release this time to change the plan. You can add another session after scheduling.`
                      : "To schedule this session, release the hold and choose a Workshop work item. You can also leave this time held and start another plan."}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button variant="secondary" size="sm" disabled={saving || scheduling} onClick={releaseHold}>
                  Release and edit
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  loading={scheduling}
                  disabled={!issue || saving || scheduling}
                  title={issue ? undefined : "Attach a Workshop work item to schedule this"}
                  onClick={scheduleHold}
                >
                  <CalendarCheck className="size-3.5" /> Schedule workshop
                </Button>
              </div>
              <p className="text-11 text-secondary sm:basis-full">
                One plan holds one time. Use “Start another plan” to keep this reservation and plan more. Return to it
                from Saved planning drafts.
              </p>
            </div>
          ) : null}
          {!isHeld ? (
            <>
              <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <h3 className="text-body-sm-medium text-primary">Matching slots</h3>
                  <p className="mt-1 text-11 text-secondary">
                    Up to {MAX_SLOTS_PER_TRAINER_PER_DAY} starts per trainer per day. Times shown in{" "}
                    {Intl.DateTimeFormat().resolvedOptions().timeZone}.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={search.state === "running"}
                    disabled={busy || !trainerIds.length || !validPlan || search.state === "running"}
                    onClick={() => void findNext(null)}
                  >
                    <CalendarSearch className="size-3.5" /> Find first available
                  </Button>
                  <span className="rounded-full bg-surface-2 px-2.5 py-1 text-11 text-secondary">
                    {candidates.length} options
                  </span>
                </div>
              </div>

              {search.state === "running" ? (
                <p className="mb-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 text-11 text-secondary">
                  Looking for a complete {formatMinutes(availability.requiredMinutes)} opening — checking from{" "}
                  {dateTimeLabel(search.from.toISOString())}.
                </p>
              ) : null}

              {search.state === "done" ? (
                <div className="mb-4 rounded-lg border border-subtle bg-layer-2 px-4 py-3 text-body-xs-regular">
                  {search.result.found ? (
                    <>
                      <p className="text-primary">
                        <span className="font-medium">{search.result.candidate.trainerName}</span> is the first who can:{" "}
                        {dateTimeLabel(search.result.candidate.workshopStartsAt)} –{" "}
                        {dateTimeLabel(search.result.candidate.workshopEndsAt)}.
                      </p>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="mt-2"
                        onClick={() => {
                          if (search.result.found) {
                            const candidate = search.result.candidate;
                            setTrainerIds((current) =>
                              current.includes(candidate.trainerId) ? current : [...current, candidate.trainerId]
                            );
                            onViewWeek(startOfWeek(new Date(candidate.workshopStartsAt)));
                          }
                        }}
                      >
                        Show this week
                      </Button>
                      {search.forTrainer ? <p className="mt-1 text-secondary">Searched that trainer only.</p> : null}
                    </>
                  ) : (
                    <div className="text-secondary">
                      <p>No matching time found up to {dateTimeLabel(search.result.searchedUntil.toISOString())}.</p>
                      <p className="mt-1">{noWorkshopFitReason(search.result.availability, spec, formatMinutes)}</p>
                    </div>
                  )}
                </div>
              ) : null}
              {capacityState === "error" ? (
                <div role="alert" className="rounded-lg border border-subtle p-4">
                  <p className="text-body-sm-medium">Availability could not be loaded</p>
                  <p className="mt-1 text-body-xs-regular text-secondary">{capacityError}</p>
                  <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
                    Retry
                  </Button>
                </div>
              ) : capacityState === "loading" ? (
                <p role="status" className="rounded-lg border border-subtle p-4 text-body-xs-regular text-secondary">
                  Loading availability for this week…
                </p>
              ) : candidateDays.length ? (
                <div className="space-y-6">
                  {candidateDays.map((group) => (
                    <section key={group.day} aria-label={dayLabel(group.candidates[0].workshopStartsAt)}>
                      <h4 className="mb-2 text-11 font-semibold tracking-[0.12em] text-placeholder uppercase">
                        {dayLabel(group.candidates[0].workshopStartsAt)}
                      </h4>
                      <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                        {group.candidates.map((candidate) => (
                          <article
                            key={`${candidate.trainerId}-${candidate.blockedStartsAt}`}
                            className="rounded-lg border border-subtle bg-surface-2 p-4"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <h4 className="text-body-sm-medium text-primary">{candidate.trainerName}</h4>
                                <p className="mt-0.5 text-11 text-placeholder">{candidate.timezone}</p>
                              </div>
                              {candidate.availabilityStatus !== "fresh" ? (
                                <span className="text-11 text-warning-primary">Verify calendar</span>
                              ) : null}
                            </div>
                            <div className="mt-4 space-y-2 text-body-xs-regular">
                              <div className="flex items-start gap-2">
                                <CalendarSearch className="mt-0.5 size-3.5 shrink-0 text-accent-primary" />
                                <div>
                                  <span className="block text-11 text-placeholder">Workshop</span>
                                  <span className="text-primary">
                                    {timeLabel(candidate.workshopStartsAt)} – {timeLabel(candidate.workshopEndsAt)}
                                  </span>
                                </div>
                              </div>
                              <div className="flex items-start gap-2">
                                <Clock3 className="mt-0.5 size-3.5 shrink-0 text-secondary" />
                                <div>
                                  <span className="block text-11 text-placeholder">Trainer blocked</span>
                                  <span className="text-secondary">
                                    {/* Spelled out in full when travel pushes the block onto
                              another day, which the heading above would otherwise
                              contradict. */}
                                    {sameLocalDay(candidate.blockedStartsAt, candidate.workshopStartsAt)
                                      ? timeLabel(candidate.blockedStartsAt)
                                      : dateTimeLabel(candidate.blockedStartsAt)}{" "}
                                    –{" "}
                                    {sameLocalDay(candidate.blockedEndsAt, candidate.workshopStartsAt)
                                      ? timeLabel(candidate.blockedEndsAt)
                                      : dateTimeLabel(candidate.blockedEndsAt)}
                                  </span>
                                </div>
                              </div>
                            </div>
                            <Button
                              className="mt-4 w-full"
                              variant="secondary"
                              size="sm"
                              disabled={!validPlan || busy}
                              onClick={() => holdCandidate(candidate)}
                            >
                              <ShieldCheck className="size-3.5" />{" "}
                              {planNeedsSaving ? "Save plan & hold for 72h" : "Hold for 72h"}
                            </Button>
                            {planNeedsSaving ? (
                              <p className="mt-2 text-center text-11 text-placeholder">
                                Saves this plan and temporarily reserves the full trainer block.
                              </p>
                            ) : null}
                          </article>
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="grid min-h-48 place-items-center rounded-lg border border-dashed border-subtle bg-surface-2 px-5 text-center">
                  <div>
                    <CalendarSearch className="mx-auto size-7 text-placeholder" />
                    <h3 className="mt-2 text-body-sm-medium text-primary">No matching time this week</h3>
                    <p className="mt-1 text-body-xs-regular text-secondary">
                      {noWorkshopFitReason(availability, spec, formatMinutes)}
                    </p>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}
