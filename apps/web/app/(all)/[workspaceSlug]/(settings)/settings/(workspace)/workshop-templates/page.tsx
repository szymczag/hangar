/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
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
import { useMember } from "@/hooks/store/use-member";
import { CapacityService } from "@/services/capacity.service";
import type {
  TChecklistAssigneeMode,
  TWorkshopChecklistItem,
  TWorkshopChecklistTemplate,
  TWorkshopRole,
} from "@/services/capacity.service";

const service = new CapacityService();

const ASSIGNEE_MODES: Array<{ value: TChecklistAssigneeMode; label: string }> = [
  { value: "unassigned", label: "Nobody yet" },
  { value: "workshop_trainer", label: "The workshop's trainer" },
  { value: "role", label: "Whoever holds a role" },
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
  role_id: null,
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

function offsetHint(days: number) {
  if (days === 0) return "on the day";
  if (days === -1) return "the day before";
  if (days === 1) return "the day after";
  return days < 0 ? `${Math.abs(days)} days before` : `${days} days after`;
}

const inputStyle =
  "h-9 rounded-md border border-subtle bg-surface-2 px-2.5 text-body-sm-regular outline-none focus:border-accent-primary";

/**
 * The subtasks a Workshop starts with, and who does them.
 *
 * Roles come first on the page because templates point at them: a checklist item
 * says "whoever handles streaming", and this is where that resolves to people.
 * Naming the job rather than the person is what lets the rota change without
 * anybody editing a template.
 */
const WorkshopTemplatesSettingsPage = observer(function WorkshopTemplatesSettingsPage() {
  const { workspaceSlug } = useParams();
  const slug = workspaceSlug?.toString();
  const { config } = useInstance();
  const featureEnabled = config?.is_google_calendar_capacity_enabled === true;
  const {
    workspace: { fetchWorkspaceMembers, workspaceMemberIds, getWorkspaceMemberDetails },
  } = useMember();

  useSWR(slug && featureEnabled ? `WORKSPACE_MEMBERS_${slug}` : null, slug ? () => fetchWorkspaceMembers(slug) : null, {
    revalidateOnFocus: false,
  });

  const { data: roleData, mutate: mutateRoles } = useSWR(
    slug && featureEnabled ? `WORKSHOP_ROLES_${slug}` : null,
    slug ? () => service.listWorkshopRoles(slug) : null,
    { revalidateOnFocus: false }
  );
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
  const [newRoleName, setNewRoleName] = useState("");
  const [busyRole, setBusyRole] = useState<string | null>(null);

  const templates = data?.results ?? [];
  const roles = roleData?.results ?? [];
  const selected = templates.find((template) => template.id === selectedId) ?? null;
  const memberIds = workspaceMemberIds ?? [];

  const memberName = (userId: string) => {
    const details = getWorkspaceMemberDetails(userId);
    return details?.member?.display_name ?? details?.member?.email ?? "Unknown person";
  };

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

  const removeTemplate = async (template: TWorkshopChecklistTemplate) => {
    if (!slug) return;
    if (!window.confirm(`Delete “${template.name}”? Subtasks it already created are kept.`)) return;
    try {
      await service.deleteChecklistTemplate(slug, template.id);
      if (selectedId === template.id) setSelectedId(null);
      await mutate();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Template not deleted", message: errorMessage(error, "Try again.") });
    }
  };

  const addRole = async () => {
    if (!slug || !newRoleName.trim()) return;
    setBusyRole("new");
    try {
      await service.createWorkshopRole(slug, { name: newRoleName.trim(), member_ids: [] });
      setNewRoleName("");
      await mutateRoles();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Role not created", message: errorMessage(error, "Try again.") });
    } finally {
      setBusyRole(null);
    }
  };

  const toggleRoleMember = async (role: TWorkshopRole, userId: string) => {
    if (!slug) return;
    const nextMembers = role.member_ids.includes(userId)
      ? role.member_ids.filter((value) => value !== userId)
      : [...role.member_ids, userId];
    setBusyRole(role.id);
    try {
      await service.updateWorkshopRole(slug, role.id, { name: role.name, member_ids: nextMembers });
      await mutateRoles();
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Role not saved", message: errorMessage(error, "Try again.") });
    } finally {
      setBusyRole(null);
    }
  };

  const removeRole = async (role: TWorkshopRole) => {
    if (!slug) return;
    if (!window.confirm(`Delete the role “${role.name}”? Checklist items using it become unassigned.`)) return;
    setBusyRole(role.id);
    try {
      await service.deleteWorkshopRole(slug, role.id);
      await Promise.all([mutateRoles(), mutate()]);
    } catch (error: unknown) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Role not deleted", message: errorMessage(error, "Try again.") });
    } finally {
      setBusyRole(null);
    }
  };

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <SettingsContentWrapper>
      <PageHead title="Workshop checklists" />
      <div className="flex flex-col gap-8">
        <div>
          <h3 className="text-xl font-medium">Workshop checklists</h3>
          <p className="mt-1 text-body-xs-regular text-secondary">
            The subtasks a Workshop starts with. Due dates are counted from the workshop&apos;s first session, so a
            template stays correct however often the date moves.
          </p>
        </div>

        <section aria-label="Workshop roles" className="flex flex-col gap-4">
          <div>
            <h4 className="text-body-sm-medium">Roles</h4>
            <p className="mt-1 text-body-xs-regular text-secondary">
              A standing job and whoever currently does it. Templates point at the role, so when the rota changes you
              edit it here once instead of editing every template.
            </p>
          </div>

          <div className="flex flex-col gap-3">
            {roles.map((role) => (
              <div key={role.id} className="rounded-xl border border-subtle bg-surface-1 p-4">
                <div className="flex items-center gap-3">
                  <span className="text-body-sm-medium">{role.name}</span>
                  <span className="text-body-xs-regular text-secondary">
                    {role.member_ids.length === 0
                      ? "nobody yet"
                      : role.member_ids.map((userId) => memberName(userId)).join(", ")}
                  </span>
                  <button
                    type="button"
                    aria-label={`Delete role ${role.name}`}
                    disabled={busyRole === role.id}
                    className="ml-auto text-secondary hover:text-danger-primary"
                    onClick={() => void removeRole(role)}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                  {memberIds.map((userId) => (
                    <label key={userId} className="flex items-center gap-2 text-body-xs-regular">
                      <input
                        type="checkbox"
                        checked={role.member_ids.includes(userId)}
                        disabled={busyRole === role.id}
                        onChange={() => void toggleRoleMember(role, userId)}
                      />
                      {memberName(userId)}
                    </label>
                  ))}
                </div>
              </div>
            ))}

            <div className="flex items-end gap-2">
              <label className="flex flex-col gap-1 text-body-xs-regular">
                <span className="text-secondary">New role</span>
                <input
                  className={`${inputStyle} w-64`}
                  value={newRoleName}
                  maxLength={80}
                  placeholder="Streaming"
                  onChange={(event) => setNewRoleName(event.target.value)}
                />
              </label>
              <Button
                variant="secondary"
                size="sm"
                disabled={!newRoleName.trim() || busyRole === "new"}
                onClick={() => void addRole()}
              >
                <Plus className="mr-1 size-4" />
                Add role
              </Button>
            </div>
          </div>
        </section>

        <section aria-label="Checklist templates" className="flex flex-col gap-4">
          <h4 className="text-body-sm-medium">Templates</h4>

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
                    onClick={() => void removeTemplate(template)}
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
            <div className="flex flex-col gap-4 rounded-xl border border-subtle bg-surface-1 p-5">
              <div className="flex flex-wrap items-end gap-4">
                <label className="flex flex-col gap-1 text-body-xs-regular">
                  <span className="text-secondary">Template name</span>
                  <input
                    className={`${inputStyle} w-72`}
                    value={name}
                    maxLength={120}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>
                <label className="flex items-center gap-2 pb-2 text-body-xs-regular">
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
                        className={inputStyle}
                        value={item.title}
                        maxLength={255}
                        onChange={(event) => patchItem(index, { title: event.target.value })}
                      />
                    </label>

                    <label className="flex flex-col gap-1 text-body-xs-regular">
                      <span className="text-secondary">Assigned to</span>
                      <select
                        className={inputStyle}
                        value={item.assignee_mode}
                        onChange={(event) => {
                          const mode = event.target.value as TChecklistAssigneeMode;
                          patchItem(index, {
                            assignee_mode: mode,
                            assignee_id: mode === "fixed" ? (item.assignee_id ?? memberIds[0] ?? null) : null,
                            role_id: mode === "role" ? (item.role_id ?? roles[0]?.id ?? null) : null,
                          });
                        }}
                      >
                        {ASSIGNEE_MODES.map((mode) => (
                          <option key={mode.value} value={mode.value}>
                            {mode.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    {item.assignee_mode === "fixed" && (
                      <label className="flex flex-col gap-1 text-body-xs-regular">
                        <span className="text-secondary">Person</span>
                        <select
                          className={inputStyle}
                          value={item.assignee_id ?? ""}
                          onChange={(event) => patchItem(index, { assignee_id: event.target.value || null })}
                        >
                          <option value="">Choose a person</option>
                          {memberIds.map((userId) => (
                            <option key={userId} value={userId}>
                              {memberName(userId)}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}

                    {item.assignee_mode === "role" && (
                      <label className="flex flex-col gap-1 text-body-xs-regular">
                        <span className="text-secondary">Role</span>
                        <select
                          className={inputStyle}
                          value={item.role_id ?? ""}
                          onChange={(event) => patchItem(index, { role_id: event.target.value || null })}
                        >
                          <option value="">Choose a role</option>
                          {roles.map((role) => (
                            <option key={role.id} value={role.id}>
                              {role.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}

                    <label className="flex flex-col gap-1 text-body-xs-regular">
                      <span className="text-secondary">Days from the workshop</span>
                      <div className="flex items-center gap-2">
                        <input
                          type="number"
                          className={`${inputStyle} w-24 text-right`}
                          value={item.offset_days}
                          min={-365}
                          max={365}
                          onChange={(event) => patchItem(index, { offset_days: Number(event.target.value) })}
                        />
                        <span className="text-secondary">{offsetHint(item.offset_days)}</span>
                      </div>
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
            </div>
          ) : null}
        </section>
      </div>
    </SettingsContentWrapper>
  );
});

export default WorkshopTemplatesSettingsPage;
