/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "react-router";
import useSWR from "swr";
import { Button } from "@makeplane/propel/components/button";
import { Checkbox } from "@makeplane/propel/components/checkbox";
import { CheckboxField } from "@makeplane/propel/components/checkbox-field";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { InputField } from "@makeplane/propel/components/input-field";
import { SelectField } from "@makeplane/propel/components/select-field";
import { AddOutline, DeleteOutline } from "@makeplane/propel/icons";
import { ConfirmDialog } from "@plane/blocks/dialog";
import { Loader } from "@plane/blocks/skeleton";
import { setToast } from "@plane/blocks/toast";
import { PageHead } from "@/components/core/page-title";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
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

/** What the confirmation dialog is about to delete, if anything. */
type TPendingDeletion =
  | { kind: "template"; template: TWorkshopChecklistTemplate }
  | { kind: "role"; role: TWorkshopRole }
  | null;

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
  const [pendingDeletion, setPendingDeletion] = useState<TPendingDeletion>(null);
  const [deleting, setDeleting] = useState(false);

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
      setToast({ type: "success", title: "Template saved" });
    } catch (error: unknown) {
      setToast({
        type: "error",
        title: "Template not saved",
        message: errorMessage(error, "Check the checklist items and try again."),
      });
    } finally {
      setSaving(false);
    }
  };

  const removeTemplate = async (template: TWorkshopChecklistTemplate) => {
    if (!slug) return;
    try {
      await service.deleteChecklistTemplate(slug, template.id);
      if (selectedId === template.id) setSelectedId(null);
      await mutate();
    } catch (error: unknown) {
      setToast({ type: "error", title: "Template not deleted", message: errorMessage(error, "Try again.") });
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
      setToast({ type: "error", title: "Role not created", message: errorMessage(error, "Try again.") });
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
      setToast({ type: "error", title: "Role not saved", message: errorMessage(error, "Try again.") });
    } finally {
      setBusyRole(null);
    }
  };

  const removeRole = async (role: TWorkshopRole) => {
    if (!slug) return;
    setBusyRole(role.id);
    try {
      await service.deleteWorkshopRole(slug, role.id);
      await Promise.all([mutateRoles(), mutate()]);
    } catch (error: unknown) {
      setToast({ type: "error", title: "Role not deleted", message: errorMessage(error, "Try again.") });
    } finally {
      setBusyRole(null);
    }
  };

  const confirmDeletion = async () => {
    if (!pendingDeletion) return;
    setDeleting(true);
    try {
      if (pendingDeletion.kind === "template") await removeTemplate(pendingDeletion.template);
      else await removeRole(pendingDeletion.role);
    } finally {
      setDeleting(false);
      setPendingDeletion(null);
    }
  };

  const assigneeModeOptions = ASSIGNEE_MODES.map((mode) => ({ value: mode.value, label: mode.label }));
  const memberOptions = memberIds.map((userId) => ({ value: userId, label: memberName(userId) }));
  const roleOptions = roles.map((role) => ({ value: role.id, label: role.name }));

  if (config && !featureEnabled) return <NotAuthorizedView section="settings" className="h-auto" />;

  return (
    <SettingsContentWrapper>
      <PageHead title="Workshop checklists" />
      <div className="flex flex-col gap-8">
        <SettingsHeading
          title="Workshop checklists"
          description="The subtasks a Workshop starts with. Due dates are counted from the workshop's first session, so a template stays correct however often the date moves."
        />

        <section aria-label="Workshop roles" className="flex flex-col gap-4">
          <SettingsHeading
            variant="h5"
            title="Roles"
            description="A standing job and whoever currently does it. Templates point at the role, so when the rota changes you edit it here once instead of editing every template."
          />

          <div className="flex flex-col gap-3">
            {roles.map((role) => (
              <div key={role.id} className="rounded-lg border border-subtle bg-layer-1 p-4">
                <div className="flex items-center gap-3">
                  <span className="text-body-sm-medium text-primary">{role.name}</span>
                  <span className="text-body-xs-regular text-secondary">
                    {role.member_ids.length === 0
                      ? "nobody yet"
                      : role.member_ids.map((userId) => memberName(userId)).join(", ")}
                  </span>
                  <span className="ml-auto">
                    <IconButton
                      variant="ghost"
                      size="sm"
                      icon={<Icon icon={DeleteOutline} />}
                      aria-label={`Delete role ${role.name}`}
                      disabled={busyRole === role.id}
                      onClick={() => setPendingDeletion({ kind: "role", role })}
                    />
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
                  {memberIds.map((userId) => (
                    <Checkbox
                      key={userId}
                      label={memberName(userId)}
                      checked={role.member_ids.includes(userId)}
                      disabled={busyRole === role.id}
                      onCheckedChange={() => void toggleRoleMember(role, userId)}
                    />
                  ))}
                </div>
              </div>
            ))}

            <div className="flex items-end gap-2">
              <div className="w-64">
                <InputField
                  size="lg"
                  orientation="vertical"
                  label="New role"
                  value={newRoleName}
                  maxLength={80}
                  placeholder="Streaming"
                  onChange={(event) => setNewRoleName(event.target.value)}
                />
              </div>
              <Button
                variant="secondary"
                size="lg"
                stretch="auto"
                icon={<Icon icon={AddOutline} />}
                label="Add role"
                disabled={!newRoleName.trim() || busyRole === "new"}
                onClick={() => void addRole()}
              />
            </div>
          </div>
        </section>

        <section aria-label="Checklist templates" className="flex flex-col gap-4">
          <SettingsHeading variant="h5" title="Templates" />

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
                    size="md"
                    stretch="auto"
                    label={`${template.name}${template.is_default ? " · default" : ""}`}
                    onClick={() => setSelectedId(template.id)}
                  />
                  <IconButton
                    variant="ghost"
                    size="sm"
                    icon={<Icon icon={DeleteOutline} />}
                    aria-label={`Delete ${template.name}`}
                    onClick={() => setPendingDeletion({ kind: "template", template })}
                  />
                </div>
              ))}
              <Button
                variant="secondary"
                size="md"
                stretch="auto"
                icon={<Icon icon={AddOutline} />}
                label="New template"
                onClick={startNew}
              />
            </div>
          )}

          {items.length > 0 || selectedId ? (
            <div className="flex flex-col gap-4 rounded-lg border border-subtle bg-layer-1 p-5">
              <div className="flex flex-wrap items-end gap-4">
                <div className="w-72">
                  <InputField
                    size="lg"
                    orientation="vertical"
                    label="Template name"
                    value={name}
                    maxLength={120}
                    onChange={(event) => setName(event.target.value)}
                  />
                </div>
                <div className="pb-2">
                  <CheckboxField
                    name="is-default"
                    size="lg"
                    label="Apply to new Workshops automatically"
                    checked={isDefault}
                    onCheckedChange={(checked) => setIsDefault(checked)}
                  />
                </div>
              </div>

              <ol className="flex flex-col gap-3">
                {items.map((item, index) => (
                  <li key={item.uid} className="flex flex-wrap items-end gap-3 border-t border-subtle pt-3">
                    <div className="min-w-60 flex-1">
                      <InputField
                        size="lg"
                        orientation="vertical"
                        label="Subtask"
                        value={item.title}
                        maxLength={255}
                        onChange={(event) => patchItem(index, { title: event.target.value })}
                      />
                    </div>

                    <SelectField<TChecklistAssigneeMode>
                      label="Assigned to"
                      size="lg"
                      width="fit"
                      options={assigneeModeOptions}
                      value={item.assignee_mode}
                      onValueChange={(mode) => {
                        if (mode === null) return;
                        patchItem(index, {
                          assignee_mode: mode,
                          assignee_id: mode === "fixed" ? (item.assignee_id ?? memberIds[0] ?? null) : null,
                          role_id: mode === "role" ? (item.role_id ?? roles[0]?.id ?? null) : null,
                        });
                      }}
                    />

                    {item.assignee_mode === "fixed" && (
                      <SelectField<string>
                        label="Person"
                        size="lg"
                        width="fit"
                        placeholder="Choose a person"
                        options={memberOptions}
                        value={item.assignee_id}
                        onValueChange={(userId) => patchItem(index, { assignee_id: userId || null })}
                      />
                    )}

                    {item.assignee_mode === "role" && (
                      <SelectField<string>
                        label="Role"
                        size="lg"
                        width="fit"
                        placeholder="Choose a role"
                        options={roleOptions}
                        value={item.role_id}
                        onValueChange={(roleId) => patchItem(index, { role_id: roleId || null })}
                      />
                    )}

                    <div className="flex items-end gap-2">
                      <div className="w-40">
                        <InputField
                          size="lg"
                          orientation="vertical"
                          type="number"
                          label="Days from the workshop"
                          value={item.offset_days}
                          min={-365}
                          max={365}
                          onChange={(event) => patchItem(index, { offset_days: Number(event.target.value) })}
                        />
                      </div>
                      <span className="pb-2 text-body-xs-regular whitespace-nowrap text-secondary">
                        {offsetHint(item.offset_days)}
                      </span>
                    </div>

                    <div className="pb-1">
                      <IconButton
                        variant="ghost"
                        size="sm"
                        icon={<Icon icon={DeleteOutline} />}
                        aria-label={`Remove subtask ${index + 1}`}
                        onClick={() => setItems((current) => current.filter((_, position) => position !== index))}
                      />
                    </div>
                  </li>
                ))}
              </ol>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="md"
                  stretch="auto"
                  icon={<Icon icon={AddOutline} />}
                  label="Add subtask"
                  onClick={() =>
                    setItems((current) => [...current, withUid({ ...BLANK_ITEM, position: current.length })])
                  }
                />
                <Button
                  variant="primary"
                  size="md"
                  stretch="auto"
                  label="Save template"
                  loading={saving}
                  onClick={() => void save()}
                />
              </div>
            </div>
          ) : null}
        </section>
      </div>
      <ConfirmDialog
        isOpen={pendingDeletion !== null}
        handleClose={() => setPendingDeletion(null)}
        handleSubmit={confirmDeletion}
        isSubmitting={deleting}
        primaryButtonText={{ default: "Delete", loading: "Deleting" }}
        title={
          pendingDeletion?.kind === "role"
            ? `Delete the role “${pendingDeletion.role.name}”?`
            : `Delete “${pendingDeletion?.template.name ?? ""}”?`
        }
        content={
          pendingDeletion?.kind === "role"
            ? "Checklist items using it become unassigned."
            : "Subtasks it already created are kept."
        }
      />
    </SettingsContentWrapper>
  );
});

export default WorkshopTemplatesSettingsPage;
