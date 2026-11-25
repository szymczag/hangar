// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import { useViewerTimezone } from "../shared/viewer-timezone";
import { useState } from "react";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { SearchOutline } from "@makeplane/propel/icons";
import type { TWorkshopPlanDraft } from "@/services/capacity.service";
import { dateTimeLabel } from "./workshop-planner.utils";

export function PlanToolbar({
  drafts,
  currentId,
  dirty,
  busy,
  canSave,
  onSave,
  onSelect,
  onDelete,
}: {
  drafts: TWorkshopPlanDraft[];
  currentId: string | null;
  dirty: boolean;
  busy: boolean;
  canSave: boolean;
  onSave: () => void;
  onSelect: (draft: TWorkshopPlanDraft | null) => void;
  onDelete: () => void;
}) {
  const timeZone = useViewerTimezone();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const current = drafts.find((draft) => draft.id === currentId);
  return (
    <header className="space-y-4 border-b border-subtle p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-primary">Workshop planner</h2>
          <p className="mt-1 text-body-xs-regular text-secondary">Find a trainer and reserve or schedule a workshop.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            stretch="auto"
            label="Saved plans"
            disabled={busy}
            onClick={() => setOpen(!open)}
            aria-expanded={open}
          />
          <Button
            variant="secondary"
            size="sm"
            stretch="auto"
            label="New plan"
            disabled={busy}
            onClick={() => onSelect(null)}
          />
        </div>
      </div>
      {open && (
        <div className="rounded-lg border border-subtle p-3">
          <div className="mb-2">
            <InputGroup size="lg">
              <Icon icon={SearchOutline} tint="placeholder" />
              <Input
                size="lg"
                type="text"
                aria-label="Search saved plans"
                placeholder="Search saved plans"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </InputGroup>
          </div>
          <ul aria-label="Saved plans" className="max-h-64 space-y-1 overflow-y-auto">
            {drafts
              .filter((draft) =>
                `${draft.title} ${draft.issue?.name ?? ""}`.toLowerCase().includes(query.toLowerCase())
              )
              .map((draft) => (
                <li key={draft.id}>
                  <button
                    type="button"
                    disabled={busy}
                    aria-current={draft.id === currentId ? "true" : undefined}
                    onClick={() => {
                      onSelect(draft);
                      setOpen(false);
                    }}
                    className="w-full rounded px-3 py-2 text-left hover:bg-surface-2"
                  >
                    <span className="block text-body-sm-medium">
                      {draft.title}
                      {draft.issue ? ` · ${draft.issue.project_identifier}-${draft.issue.sequence_id}` : ""}
                    </span>
                    <span className="block text-body-xs-regular text-secondary">
                      {draft.created_at ? `Created ${dateTimeLabel(draft.created_at, undefined, timeZone)} · ` : ""}
                      Updated {dateTimeLabel(draft.updated_at, undefined, timeZone)}
                    </span>
                    {draft.hold && (
                      <span className="block text-body-xs-regular text-accent-primary">
                        Session {dateTimeLabel(draft.hold.workshop_starts_at, undefined, timeZone)} · Reserved until{" "}
                        {dateTimeLabel(draft.hold.expires_at, undefined, timeZone)}
                      </span>
                    )}
                    {!draft.hold && draft.last_session && (
                      <span className="block text-body-xs-regular text-secondary">
                        Scheduled {dateTimeLabel(draft.last_session.starts_at, undefined, timeZone)}
                      </span>
                    )}
                  </button>
                </li>
              ))}
          </ul>
          {!drafts.length && <p className="text-body-xs-regular text-secondary">No saved plans yet.</p>}
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-body-sm-medium">{current?.title ?? "New plan"}</p>
          <p role="status" className="text-body-xs-regular text-secondary">
            {dirty ? "Unsaved changes" : current ? "All changes saved" : "Not saved yet"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="primary"
            size="sm"
            stretch="auto"
            label="Save changes"
            disabled={!canSave || busy || !dirty}
            onClick={onSave}
          />
          {currentId && (
            <Button
              variant="secondary"
              size="sm"
              stretch="auto"
              label="Delete plan"
              disabled={busy}
              onClick={onDelete}
            />
          )}
        </div>
      </div>
    </header>
  );
}
