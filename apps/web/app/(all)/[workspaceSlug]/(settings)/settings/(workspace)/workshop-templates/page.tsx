/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useParams } from "react-router";
import useSWR from "swr";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Loader } from "@plane/ui";
import { PageHead } from "@/components/core/page-title";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { useInstance } from "@/hooks/store/use-instance";
import { CapacityService } from "@/services/capacity.service";
import type {
  TChecklistAssigneeMode,
  TWorkshopChecklistItem,
  TWorkshopChecklistTemplate,
} from "@/services/capacity.service";

const service = new CapacityService();

const ASSIGNEE_MODES: Array<{ value: TChecklistAssigneeMode; label: string }> = [
  { value: "unassigned", label: "Nobody yet" },
  { value: "workshop_trainer", label: "The workshop's trainer" },
  { value: "fixed", label: "A specific person" },
];

/**
 * A row identity that survives editing.
 *
 * Saved items have a server id, but a row being typed into does not, and the
 * position is not an identity either -- reordering or deleting a row would hand
 * its key to a different row and React would reuse the wrong input's state.
 */
type TDraftItem = Omit<TWorkshopChecklistItem, "id"> & { uid: string };

let nextUid = 0;
const withUid = (item: Omit<TWorkshopChecklistItem, "id">): TDraftItem => ({
  ...item,
  uid: `item-${(nextUid += 1)}`,
});

const BLANK_ITEM: Omit<TWorkshopChecklistItem, "id"> = {
  position: 0,
  title: "",
  description: "",
  assignee_id: null,
  assignee_mode: "unassigned",
  offset_days: 0,
};

function errorMessage(error: unknown, fallback: string) {
  if (error && typeof error === "object") {
    const payload = error as { error?: string; detail?: string };
    if (typeof payload.error === "string") return payload.error;
    if (typeof payload.detail === "string") return payload.detail;
  }
  return fallback;
}

/**
 * The subtasks a Workshop starts with.
 *
 * One template per kind of workshop, applied when the work item is created and
 * dated when it is scheduled. Offsets rather than dates, because a template
 * outlives every workshop it produces: "seven days before" stays true, a date
 * does not.
 */
export default function WorkshopTemplatesSettingsPage() {
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString();
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;

  const { data, mutate, isLoading } = useSWR(
    slug && featureEnabled ? `WORKSHOP_CHECKLIST_TEMPLATES_${slug}` : null,
    slug ? () => service.listChecklistTemplates(slug) : null,
    { revalidateOnFocus: false }
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [isDefault, setIsDefault] = useState(false);
  const [items, setItems] = useState<TDraftItem[]>([]);
  const [saving, setSaving] = useState(false);

  const templates = data?.results ?? [];
  const selected = templates.find((template) => template.id === selectedId) ?? null;

  useEffect(() => {
    if (!selected) return;
    setName(selected.name);
    setIsDefault(selected.is_default);
    setItems(selected.items.map(({ id: _id, ...rest }) => withUid(rest)));
  }, [selected]);

  const startNew = () => {
    setSelectedId(null);
    setName("");
    setIsDefault(templates.length === 0);
    setItems([withUid(BLANK_ITEM)]);
  };

  const patchItem = (index: number, patch: Partial<TWorkshopChecklistItem>) =>
    setItems((current) => current.map((item, position) => (position === index ? { ...item, ...patch } : item)));

  const save = async () => {
    if (!slug) return;
    setSaving(true);
    try {
      const payload = {
        name,
        is_default: isDefault,
        items: items.map(({ uid: _uid, ...item }, position) => ({ ...item, position })),
      };
      const saved = selectedId
        ? await service.updateChecklistTemplate(slug, selectedId, payload)
        : await service.createChecklistTemplate(slug, payload);
      await mutate();
      setSelectedId(saved.id);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Template saved" });
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Template not saved",
        message: errorMessage(error, "Check the checklist items and try again."),
      });
    } finally {
      setSaving(false);
    }
  };

  const remove = async (template: TWorkshopChecklistTemplate) => {
    if (!slug) return;
    if (!window.confirm(`Delete “${template.name}”? Subtasks it already created are kept.`)) return;
    try {
      await service.deleteChecklistTemplate(slug, template.id);
      if (selectedId === template.id) setSelectedId(null);
      await mutate();
    } catch (error: unknown) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Template not deleted",
        message: errorMessage(error, "Try again."),
      });
    }
  };

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <SettingsContentWrapper>
      <PageHead title="Workshop checklists" />
      <div className="flex flex-col gap-6">
        <div>
          <h3 className="text-xl font-medium">Workshop checklists</h3>
          <p className="mt-1 text-body-xs-regular text-secondary">
            The subtasks a Workshop starts with. Due dates are counted from the workshop&apos;s first session, so a
            template stays correct however often the date moves.
          </p>
        </div>

        {isLoading ? (
          <Loader className="space-y-3">
            <Loader.Item height="40px" />
            <Loader.Item height="120px" />
          </Loader>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            {templates.map((template) => (
              <div key={template.id} className="flex items-center gap-1">
                <Button
                  variant={template.id === selectedId ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => setSelectedId(template.id)}
                >
                  {template.name}
                  {template.is_default ? " · default" : ""}
                </Button>
                <button
                  type="button"
                  aria-label={`Delete ${template.name}`}
                  className="text-secondary hover:text-danger-primary"
                  onClick={() => void remove(template)}
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
            ))}
            <Button variant="secondary" size="sm" onClick={startNew}>
              <Plus className="mr-1 size-4" />
              New template
            </Button>
          </div>
        )}

        {items.length > 0 || selectedId ? (
          <section className="flex flex-col gap-4 rounded-xl border border-subtle bg-surface-1 p-5">
            <div className="flex flex-wrap items-end gap-4">
              <label className="flex flex-col gap-1 text-body-xs-regular">
                <span className="text-secondary">Template name</span>
                <input
                  className="rounded-md border border-subtle bg-surface-2 px-2 py-1.5"
                  value={name}
                  maxLength={120}
                  onChange={(event) => setName(event.target.value)}
                />
              </label>
              <label className="flex items-center gap-2 text-body-xs-regular">
                <input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} />
                Apply to new Workshops automatically
              </label>
            </div>

            <ol className="flex flex-col gap-3">
              {items.map((item, index) => (
                <li key={item.uid} className="flex flex-wrap items-end gap-3 border-t border-subtle pt-3">
                  <label className="flex min-w-60 flex-1 flex-col gap-1 text-body-xs-regular">
                    <span className="text-secondary">Subtask</span>
                    <input
                      className="rounded-md border border-subtle bg-surface-2 px-2 py-1.5"
                      value={item.title}
                      maxLength={255}
                      onChange={(event) => patchItem(index, { title: event.target.value })}
                    />
                  </label>
                  <label className="flex flex-col gap-1 text-body-xs-regular">
                    <span className="text-secondary">Assigned to</span>
                    <select
                      className="rounded-md border border-subtle bg-surface-2 px-2 py-1.5"
                      value={item.assignee_mode}
                      onChange={(event) =>
                        patchItem(index, {
                          assignee_mode: event.target.value as TChecklistAssigneeMode,
                          assignee_id: event.target.value === "fixed" ? item.assignee_id : null,
                        })
                      }
                    >
                      {ASSIGNEE_MODES.map((mode) => (
                        <option key={mode.value} value={mode.value}>
                          {mode.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-body-xs-regular">
                    <span className="text-secondary">Days from the workshop</span>
                    <input
                      type="number"
                      className="w-32 rounded-md border border-subtle bg-surface-2 px-2 py-1.5"
                      value={item.offset_days}
                      min={-365}
                      max={365}
                      onChange={(event) => patchItem(index, { offset_days: Number(event.target.value) })}
                    />
                  </label>
                  <button
                    type="button"
                    aria-label={`Remove subtask ${index + 1}`}
                    className="pb-2 text-secondary hover:text-danger-primary"
                    onClick={() => setItems((current) => current.filter((_, position) => position !== index))}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </li>
              ))}
            </ol>

            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  setItems((current) => [...current, withUid({ ...BLANK_ITEM, position: current.length })])
                }
              >
                <Plus className="mr-1 size-4" />
                Add subtask
              </Button>
              <Button variant="primary" size="sm" loading={saving} onClick={() => void save()}>
                Save template
              </Button>
            </div>
          </section>
        ) : null}
      </div>
    </SettingsContentWrapper>
  );
}
