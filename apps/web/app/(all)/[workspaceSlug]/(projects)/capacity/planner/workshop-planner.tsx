/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useMemo, useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CalendarCheck, CalendarSearch, Clock3, Save, ShieldCheck, Trash2, Users } from "lucide-react";
import { errorMessage } from "../shared/capacity-format.utils";
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
  sameLocalDay,
  timeLabel,
  type TFirstAvailable,
  type TStartWindow,
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
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className="text-body-xs-medium text-secondary">
      {label}
      <div className="relative mt-1">
        <input
          type="number"
          min={0}
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
}: {
  workspaceSlug: string;
  trainers: TTrainerCapacity[];
  weekStart: Date;
  weekEnd: Date;
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
  const [search, setSearch] = useState<
    | { state: "idle" }
    | { state: "running"; from: Date }
    | { state: "done"; result: TFirstAvailable; forTrainer: string | null }
  >({ state: "idle" });

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
    setSearch({ state: "running", from: weekStart });
    try {
      const result = await findFirstAvailable(
        weekStart,
        {
          trainerIds: ids,
          durationMinutes,
          preparationMinutes,
          travelBeforeMinutes,
          travelAfterMinutes,
          startWindow,
        },
        async (windowStart, windowEnd) => {
          const response = await capacityService.getCapacity(
            workspaceSlug,
            windowStart.toISOString(),
            windowEnd.toISOString(),
            ids
          );
          return response.trainers;
        },
        { onProgress: (windowStart) => setSearch({ state: "running", from: windowStart }) }
      );
      setSearch({ state: "done", result, forTrainer: only });
    } catch (error: unknown) {
      setSearch({ state: "idle" });
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Could not look ahead",
        message: errorMessage(error, "The capacity service is rate-limited. Try again shortly."),
      });
    }
  };

  const candidates = useMemo(
    () =>
      findWorkshopCandidates(trainers, weekStart, weekEnd, {
        trainerIds,
        durationMinutes,
        preparationMinutes,
        travelBeforeMinutes,
        travelAfterMinutes,
        startWindow,
      }),
    [
      durationMinutes,
      preparationMinutes,
      startWindow,
      trainerIds,
      trainers,
      travelAfterMinutes,
      travelBeforeMinutes,
      weekEnd,
      weekStart,
    ]
  );
  const candidateDays = useMemo(() => groupByDay(candidates), [candidates]);

  /**
   * A held plan is frozen, because the server freezes it: `PUT /capacity/plans/`
   * answers 409 while a hold is active, so that the block someone is holding
   * still means what it said when they took it. The form reflects that rather
   * than letting you type into fields whose save is guaranteed to be refused.
   */
  const isHeld = Boolean(hold);

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

  const saveDraft = async () => {
    if (!title.trim() || !trainerIds.length) return;
    setSaving(true);
    try {
      const saved =
        draftId && revision !== null
          ? await capacityService.updateWorkshopPlanDraft(workspaceSlug, draftId, revision, payload())
          : await capacityService.createWorkshopPlanDraft(workspaceSlug, payload());
      loadDraft(saved);
      await mutateDrafts();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Planning draft saved",
        message: "You can return to this search later.",
      });
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Draft not saved",
        message: errorMessage(error, "Refresh the draft and try again."),
      });
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
      await mutateDrafts();
    } finally {
      setSaving(false);
    }
  };

  const holdCandidate = async (trainerId: string, workshopStartsAt: string) => {
    if (!draftId || revision === null) return;
    setSaving(true);
    try {
      const result = await capacityService.holdWorkshopPlan(
        workspaceSlug,
        draftId,
        revision,
        trainerId,
        workshopStartsAt
      );
      setHold(result.hold);
      setRevision(result.revision);
      await mutateDrafts();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Trainer held for 72 hours",
        message: "This is an internal hold. Nothing was written to Google Calendar.",
      });
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Slot could not be held",
        message: "Availability may have changed. Refresh capacity and choose another slot.",
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
      await mutateDrafts();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Workshop scheduled",
        message: `${hold?.trainer_name ?? "The trainer"} is booked on ${workshopLabel(result.issue)}.`,
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
      await mutateDrafts();
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
            disabled={isHeld}
            className="h-8 rounded-md border border-subtle bg-surface-2 px-2 text-body-xs-regular disabled:cursor-not-allowed disabled:opacity-60"
          >
            <option value="">New plan</option>
            {draftPage?.results.map((draft) => (
              <option key={draft.id} value={draft.id}>
                {draft.title}
              </option>
            ))}
          </select>
          <Button
            variant="primary"
            size="sm"
            loading={saving}
            disabled={isHeld || !title.trim() || !trainerIds.length}
            title={isHeld ? "Release the hold before changing this plan" : undefined}
            onClick={saveDraft}
          >
            <Save className="size-3.5" /> Save draft
          </Button>
          {draftId ? (
            <Button variant="secondary" size="sm" disabled={saving} onClick={deleteDraft}>
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
            disabled={isHeld}
            onChange={(next) => {
              setIssue(next);
              // Adopt the work item's name unless the coordinator has already
              // named the draft something of their own.
              if (next && (!title.trim() || title === issue?.name)) setTitle(next.name);
            }}
          />
          <label className="block text-body-xs-medium text-secondary">
            Draft name
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. NetSec workshop"
              maxLength={255}
              disabled={isHeld}
              className="mt-1 h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 text-body-sm-regular text-primary disabled:cursor-not-allowed disabled:opacity-60"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Delivery" value={durationMinutes} onChange={setDurationMinutes} disabled={isHeld} />
            <NumberField
              label="Preparation"
              value={preparationMinutes}
              onChange={setPreparationMinutes}
              disabled={isHeld}
            />
            <NumberField
              label="Travel before"
              value={travelBeforeMinutes}
              onChange={setTravelBeforeMinutes}
              disabled={isHeld}
            />
            <NumberField
              label="Travel back"
              value={travelAfterMinutes}
              onChange={setTravelAfterMinutes}
              disabled={isHeld}
            />
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
                    disabled={isHeld}
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
                    disabled={search.state === "running"}
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
            <div className="bg-accent-secondary/10 mb-5 flex flex-col gap-3 rounded-lg border border-accent-subtle p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex gap-3">
                <ShieldCheck className="mt-0.5 size-5 shrink-0 text-accent-primary" />
                <div>
                  <h3 className="text-body-sm-medium text-primary">{hold.trainer_name} is held</h3>
                  <p className="mt-1 text-body-xs-regular text-secondary">
                    {dateTimeLabel(hold.workshop_starts_at)} –{" "}
                    {new Date(hold.workshop_ends_at).toLocaleTimeString(undefined, { timeStyle: "short" })}. Expires{" "}
                    {dateTimeLabel(hold.expires_at)}. Internal only; no Google event was created.
                  </p>
                  <p className="mt-1 text-11 text-placeholder">
                    {issue
                      ? `Scheduling books this on ${workshopLabel(issue)} and assigns ${hold.trainer_name}. The plan is frozen until then — release the hold to change it.`
                      : "This plan is not attached to a Workshop work item, so it cannot be scheduled. Release the hold to attach one."}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button variant="secondary" size="sm" disabled={saving || scheduling} onClick={releaseHold}>
                  Release hold
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
            </div>
          ) : null}
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h3 className="text-body-sm-medium text-primary">Matching slots</h3>
              <p className="mt-1 text-11 text-secondary">
                Up to {MAX_SLOTS_PER_TRAINER_PER_DAY} starts per trainer per day, spread across each opening.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                loading={search.state === "running"}
                disabled={!trainerIds.length || search.state === "running"}
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
              Looking ahead — checking the fortnight from {dateTimeLabel(search.from.toISOString())}. One window at a
              time, because the capacity service is rate-limited.
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
                  <p className="mt-1 text-secondary">
                    {search.result.windowsSearched === 1
                      ? "It is in the week already on screen, below."
                      : `Not in the week on screen — move to ${dateTimeLabel(search.result.windowStart.toISOString())} to hold it.`}
                    {search.forTrainer ? " Searched that trainer only." : ""}
                  </p>
                </>
              ) : (
                <p className="text-secondary">
                  Nothing fits in the next {search.result.windowsSearched} fortnights, up to{" "}
                  {dateTimeLabel(search.result.searchedUntil.toISOString())}
                  {search.forTrainer ? " for that trainer" : ""}. Shorten the workshop, trim the buffers, or widen the
                  eligible trainers.
                </p>
              )}
            </div>
          ) : null}
          {candidateDays.length ? (
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
                          disabled={planNeedsSaving || revision === null || saving || Boolean(hold)}
                          onClick={() => holdCandidate(candidate.trainerId, candidate.workshopStartsAt)}
                        >
                          <ShieldCheck className="size-3.5" /> Hold for 72h
                        </Button>
                        {planNeedsSaving ? (
                          <p className="mt-2 text-center text-11 text-placeholder">
                            Save this version of the plan first
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
                <h3 className="mt-2 text-body-sm-medium text-primary">No complete block fits</h3>
                <p className="mt-1 text-body-xs-regular text-secondary">
                  {startWindow === "any"
                    ? "Select more trainers, shorten the workshop or buffers, or move to another week."
                    : "Nothing fits in that half of the day. Try “Any time”, select more trainers, or move to another week."}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
