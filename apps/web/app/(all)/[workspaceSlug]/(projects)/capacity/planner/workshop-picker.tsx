/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 */

import { useState } from "react";
import useSWR from "swr";
import { Briefcase, Check, ChevronDown, X } from "lucide-react";
import { CapacityService, type TPlanIssue } from "@/services/capacity.service";

const capacityService = new CapacityService();

/** `TRN-14 · NetSec workshop`, the way a work item is named out loud. */
export const workshopLabel = (issue: TPlanIssue) => `${issue.project_identifier}-${issue.sequence_id} · ${issue.name}`;

/**
 * Which Workshop work item this plan is for.
 *
 * The planner used to open on a free-text "What" field, which meant the answer
 * it produced had nowhere to go: a title typed here matched nothing, so the
 * trainer and the time were retyped into a work item by hand. Choosing the work
 * item up front is what lets the hold be spent instead.
 *
 * Unattached stays available, because "could we fit this at all?" is a real
 * question to ask before anyone has raised a Workshop. Such a plan can be saved
 * and held; only scheduling is refused, and the hold banner says so.
 */
export function WorkshopPicker({
  workspaceSlug,
  value,
  onChange,
  disabled = false,
}: {
  workspaceSlug: string;
  value: TPlanIssue | null;
  onChange: (issue: TPlanIssue | null) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  // Keyed by the query, so SWR caches each search rather than refetching the
  // empty one every time the list is reopened.
  const { data, isLoading } = useSWR(open ? ["capacity-workshops", workspaceSlug, query] : null, () =>
    capacityService.searchWorkshops(workspaceSlug, query)
  );

  return (
    <div className="relative">
      <span className="text-body-xs-medium text-secondary">What</span>
      {/* The clear control is a sibling rather than nested inside the opener:
          a button inside a button is not focusable on its own, and screen
          readers flatten the pair into one confusing control. */}
      <div className="mt-1 flex h-10 w-full items-center rounded-md border border-subtle bg-surface-1 pr-2">
        <button
          type="button"
          disabled={disabled}
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
          className="flex min-w-0 flex-1 items-center gap-2 px-3 text-left text-body-sm-regular text-primary disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Briefcase className="size-3.5 shrink-0 text-tertiary" />
          <span className={`min-w-0 flex-1 truncate ${value ? "" : "text-placeholder"}`}>
            {value ? workshopLabel(value) : "Choose a Workshop work item"}
          </span>
        </button>
        {value && !disabled ? (
          <button
            type="button"
            aria-label="Detach the work item"
            className="shrink-0 rounded p-0.5 text-tertiary hover:text-primary"
            onClick={() => onChange(null)}
          >
            <X className="size-3.5" />
          </button>
        ) : (
          <ChevronDown className="size-3.5 shrink-0 text-tertiary" />
        )}
      </div>

      {open && !disabled ? (
        <div className="shadow-lg absolute z-20 mt-1 w-full rounded-md border border-subtle bg-surface-1 p-1">
          <input
            // The input exists only because the coordinator just opened this
            // list, and searching is the only thing to do in it -- the same
            // exception the view filter dropdown takes.
            // oxlint-disable-next-line jsx_a11y/no-autofocus
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search Workshop work items"
            className="mb-1 h-8 w-full rounded border border-subtle bg-surface-2 px-2 text-body-xs-regular"
          />
          <div className="max-h-56 overflow-y-auto">
            {isLoading ? (
              <p className="px-2 py-3 text-11 text-placeholder">Searching…</p>
            ) : data?.results.length ? (
              data.results.map((issue) => (
                <button
                  key={issue.id}
                  type="button"
                  onClick={() => {
                    onChange(issue);
                    setOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-body-xs-regular hover:bg-surface-2"
                >
                  <span className="min-w-0 flex-1 truncate">{workshopLabel(issue)}</span>
                  {value?.id === issue.id ? <Check className="size-3.5 shrink-0 text-accent-primary" /> : null}
                </button>
              ))
            ) : (
              <p className="px-2 py-3 text-11 text-placeholder">
                {query
                  ? "No Workshop work item matches."
                  : "No Workshop work items you can see. Raise one in a project you are a member of."}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
            className="mt-1 w-full rounded px-2 py-1.5 text-left text-11 text-secondary hover:bg-surface-2"
          >
            Plan without a work item — explore only, cannot be scheduled
          </button>
        </div>
      ) : null}
    </div>
  );
}
