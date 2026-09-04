/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useMemo, useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CalendarSearch, Clock3, Save, Trash2, Users } from "lucide-react";
import {
  CapacityService,
  type TTrainerCapacity,
  type TWorkshopPlanDraft,
  type TWorkshopPlanDraftInput,
} from "@/services/capacity.service";
import { findWorkshopCandidates } from "./workshop-planner.utils";

const capacityService = new CapacityService();

const dateTimeLabel = (value: string) =>
  new Date(value).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", timeStyle: "short" });

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="text-body-xs-medium text-secondary">
      {label}
      <div className="relative mt-1">
        <input
          type="number"
          min={0}
          step={15}
          value={value}
          onChange={(event) => onChange(Math.max(0, Number(event.target.value)))}
          className="h-9 w-full rounded-md border border-subtle bg-surface-1 px-3 pr-11 text-body-sm-regular text-primary"
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
  const [durationMinutes, setDurationMinutes] = useState(240);
  const [preparationMinutes, setPreparationMinutes] = useState(30);
  const [travelBeforeMinutes, setTravelBeforeMinutes] = useState(60);
  const [travelAfterMinutes, setTravelAfterMinutes] = useState(60);
  const [trainerIds, setTrainerIds] = useState(() => trainers.map((trainer) => trainer.trainer_id));
  const [saving, setSaving] = useState(false);

  const candidates = useMemo(
    () =>
      findWorkshopCandidates(
        trainers,
        trainerIds,
        weekStart,
        weekEnd,
        durationMinutes,
        preparationMinutes,
        travelBeforeMinutes,
        travelAfterMinutes
      ),
    [
      durationMinutes,
      preparationMinutes,
      trainerIds,
      trainers,
      travelAfterMinutes,
      travelBeforeMinutes,
      weekEnd,
      weekStart,
    ]
  );

  const payload = (): TWorkshopPlanDraftInput => ({
    title: title.trim(),
    duration_minutes: durationMinutes,
    preparation_minutes: preparationMinutes,
    travel_before_minutes: travelBeforeMinutes,
    travel_after_minutes: travelAfterMinutes,
    window_starts_at: weekStart.toISOString(),
    window_ends_at: weekEnd.toISOString(),
    trainer_ids: trainerIds,
  });

  const loadDraft = (draft: TWorkshopPlanDraft) => {
    setDraftId(draft.id);
    setRevision(draft.revision);
    setTitle(draft.title);
    setDurationMinutes(draft.duration_minutes);
    setPreparationMinutes(draft.preparation_minutes);
    setTravelBeforeMinutes(draft.travel_before_minutes);
    setTravelAfterMinutes(draft.travel_after_minutes);
    setTrainerIds(draft.trainer_ids.filter((id) => trainers.some((trainer) => trainer.trainer_id === id)));
  };

  const reset = () => {
    setDraftId(null);
    setRevision(null);
    setTitle("");
    setDurationMinutes(240);
    setPreparationMinutes(30);
    setTravelBeforeMinutes(60);
    setTravelAfterMinutes(60);
    setTrainerIds(trainers.map((trainer) => trainer.trainer_id));
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
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Draft not saved", message: "Refresh the draft and try again." });
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
            className="h-8 rounded-md border border-subtle bg-surface-2 px-2 text-body-xs-regular"
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
            disabled={!title.trim() || !trainerIds.length}
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
          <label className="block text-body-xs-medium text-secondary">
            What
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. NetSec workshop"
              maxLength={255}
              className="mt-1 h-10 w-full rounded-md border border-subtle bg-surface-1 px-3 text-body-sm-regular text-primary"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <NumberField label="Delivery" value={durationMinutes} onChange={setDurationMinutes} />
            <NumberField label="Preparation" value={preparationMinutes} onChange={setPreparationMinutes} />
            <NumberField label="Travel before" value={travelBeforeMinutes} onChange={setTravelBeforeMinutes} />
            <NumberField label="Travel back" value={travelAfterMinutes} onChange={setTravelAfterMinutes} />
          </div>
          <fieldset>
            <legend className="flex items-center gap-2 text-body-xs-medium text-secondary">
              <Users className="size-3.5" /> Eligible trainers
            </legend>
            <div className="mt-2 space-y-1.5">
              {trainers.map((trainer) => (
                <label
                  key={trainer.trainer_id}
                  className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-body-xs-regular hover:bg-surface-2"
                >
                  <input
                    type="checkbox"
                    checked={trainerIds.includes(trainer.trainer_id)}
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
                </label>
              ))}
            </div>
          </fieldset>
        </div>

        <div className="p-5">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h3 className="text-body-sm-medium text-primary">Matching slots</h3>
              <p className="mt-1 text-11 text-secondary">Earliest fit in every free range during the selected week.</p>
            </div>
            <span className="rounded-full bg-surface-2 px-2.5 py-1 text-11 text-secondary">
              {candidates.length} options
            </span>
          </div>
          {candidates.length ? (
            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {candidates.map((candidate) => (
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
                          {dateTimeLabel(candidate.workshopStartsAt)} –{" "}
                          {new Date(candidate.workshopEndsAt).toLocaleTimeString(undefined, { timeStyle: "short" })}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <Clock3 className="mt-0.5 size-3.5 shrink-0 text-secondary" />
                      <div>
                        <span className="block text-11 text-placeholder">Trainer blocked</span>
                        <span className="text-secondary">
                          {dateTimeLabel(candidate.blockedStartsAt)} –{" "}
                          {new Date(candidate.blockedEndsAt).toLocaleTimeString(undefined, { timeStyle: "short" })}
                        </span>
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="grid min-h-48 place-items-center rounded-lg border border-dashed border-subtle bg-surface-2 px-5 text-center">
              <div>
                <CalendarSearch className="mx-auto size-7 text-placeholder" />
                <h3 className="mt-2 text-body-sm-medium text-primary">No complete block fits</h3>
                <p className="mt-1 text-body-xs-regular text-secondary">
                  Select more trainers, shorten the workshop or buffers, or move to another week.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
