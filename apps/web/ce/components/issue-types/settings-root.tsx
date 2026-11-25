/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Management UI for a project's custom work item types and their properties.

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { InputField } from "@makeplane/propel/components/input-field";
import { SelectField } from "@makeplane/propel/components/select-field";
import { Switch } from "@makeplane/propel/components/switch";
import { AddOutline } from "@makeplane/propel/icons";
import { EmojiPicker, type ChangeHandlerPayload } from "@plane/blocks/emoji-icon-picker";
import { setToast } from "@plane/blocks/toast";
import type { TLogoProps } from "@plane/types";
// components
import { IssueTypeIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// plane web
import { issueTypeService } from "@/plane-web/services/issue-type.service";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import { WorkshopsCard } from "./workshops-card";
import type { TIssuePropertyExt, TIssuePropertyType, TIssueTypeExt } from "@/plane-web/types/issue-types";

const PROPERTY_TYPE_OPTIONS: { value: TIssuePropertyType; label: string }[] = [
  { value: "text", label: "Text" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "boolean", label: "Boolean" },
  { value: "select", label: "Select" },
  { value: "multi_select", label: "Multi select" },
  { value: "member", label: "Member" },
];

type Props = {
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
};

const PropertyRow = observer(function PropertyRow(props: {
  property: TIssuePropertyExt;
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
  onChanged: () => void;
}) {
  const { property, workspaceSlug, projectId, isAdmin, onChanged } = props;
  const [optionName, setOptionName] = useState("");

  const isSelect = property.property_type === "select" || property.property_type === "multi_select";

  const addOption = async () => {
    if (!optionName.trim()) return;
    try {
      await issueTypeService.createOption(workspaceSlug, projectId, property.id, { name: optionName.trim() });
      setOptionName("");
      onChanged();
    } catch {
      setToast({ type: "error", title: "Error!", message: "Failed to add the option." });
    }
  };

  return (
    <div className="flex flex-col gap-1 rounded-md border border-subtle px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-14">
          <span className="font-medium">{property.display_name}</span>
          <span className="rounded-sm bg-layer-1 px-1.5 py-0.5 text-11 text-tertiary">
            {PROPERTY_TYPE_OPTIONS.find((option) => option.value === property.property_type)?.label}
          </span>
          {property.is_required && <span className="text-11 text-danger-primary">required</span>}
          {property.system_key && (
            <span
              className="rounded-sm bg-layer-1 px-1.5 py-0.5 text-11 text-tertiary"
              title="Hangar reads this property. Rename it freely; it cannot be removed."
            >
              built in
            </span>
          )}
        </div>
      </div>
      {isSelect && (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          {(property.options ?? []).map((option) => (
            <span key={option.id} className="rounded-full bg-layer-1 px-2 py-0.5 text-11 text-secondary">
              {option.name}
            </span>
          ))}
          {isAdmin && (
            <div className="flex items-center gap-1">
              <div className="w-32">
                <InputGroup size="md">
                  <Input
                    id={`option-${property.id}`}
                    size="md"
                    type="text"
                    aria-label={`Add option to ${property.display_name}`}
                    value={optionName}
                    onChange={(e) => setOptionName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") void addOption();
                    }}
                    placeholder="Add option"
                  />
                </InputGroup>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

const toLogoProps = (value: ChangeHandlerPayload): TLogoProps =>
  value.type === "emoji"
    ? { in_use: "emoji", emoji: { value: value.value } }
    : { in_use: "icon", icon: { name: value.value.name, color: value.value.color } };

const TypeLogo = observer(function TypeLogo(props: {
  issueType: TIssueTypeExt;
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
  onChanged: () => void;
}) {
  const { issueType, workspaceSlug, projectId, isAdmin, onChanged } = props;
  const [isOpen, setIsOpen] = useState(false);
  const mark = <IssueTypeIdentifier issueTypeId={issueType.id} projectId={projectId} size="lg" />;

  if (!isAdmin) return mark;

  const updateLogo = async (value: ChangeHandlerPayload) => {
    setIsOpen(false);
    try {
      await issueTypeService.updateIssueType(workspaceSlug, projectId, issueType.id, {
        logo_props: toLogoProps(value),
      });
      onChanged();
    } catch {
      setToast({ type: "error", title: "Error!", message: "Failed to update the work item type icon." });
    }
  };

  return (
    <EmojiPicker
      iconType="material"
      isOpen={isOpen}
      handleToggle={setIsOpen}
      buttonClassName="grid size-7 place-items-center rounded-md border border-subtle hover:bg-layer-1"
      label={mark}
      onChange={(value) => void updateLogo(value)}
      defaultIconColor={issueType.logo_props?.in_use === "icon" ? issueType.logo_props.icon?.color : undefined}
      defaultOpen={issueType.logo_props?.in_use === "emoji" ? "emoji" : "icon"}
    />
  );
});

const TypeCard = observer(function TypeCard(props: {
  issueType: TIssueTypeExt;
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
  onChanged: () => void;
}) {
  const { issueType, workspaceSlug, projectId, isAdmin, onChanged } = props;
  // state
  const [isAddingProperty, setIsAddingProperty] = useState(false);
  const [propertyName, setPropertyName] = useState("");
  const [propertyType, setPropertyType] = useState<TIssuePropertyType>("text");
  const [isRequired, setIsRequired] = useState(false);

  const addProperty = async () => {
    if (!propertyName.trim()) return;
    try {
      await issueTypeService.createProperty(workspaceSlug, projectId, issueType.id, {
        display_name: propertyName.trim(),
        property_type: propertyType,
        is_required: isRequired,
        is_multi: propertyType === "multi_select",
      });
      setPropertyName("");
      setPropertyType("text");
      setIsRequired(false);
      setIsAddingProperty(false);
      onChanged();
    } catch {
      setToast({ type: "error", title: "Error!", message: "Failed to create the property." });
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-subtle p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TypeLogo
            issueType={issueType}
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            isAdmin={isAdmin}
            onChanged={onChanged}
          />
          <span className="text-16 font-medium">{issueType.name}</span>
          {issueType.is_default && <span className="text-11 text-tertiary">default</span>}
          {issueType.system_key && (
            <span className="rounded-sm bg-layer-1 px-1.5 py-0.5 text-11 text-tertiary">
              {issueType.system_key === "epic" ? "level 1" : "level 0"}
            </span>
          )}
        </div>
        {isAdmin && (
          <Button
            variant="secondary"
            size="md"
            stretch="auto"
            icon={<Icon icon={AddOutline} />}
            label="Add property"
            onClick={() => setIsAddingProperty((prev) => !prev)}
          />
        )}
      </div>
      {isAddingProperty && (
        <div className="flex flex-wrap items-end gap-2 rounded-md bg-layer-1 p-3">
          <div className="w-40">
            <InputField
              id={`new-property-${issueType.id}`}
              size="md"
              orientation="vertical"
              label="Name"
              type="text"
              value={propertyName}
              onChange={(e) => setPropertyName(e.target.value)}
              placeholder="Severity"
            />
          </div>
          <SelectField<TIssuePropertyType>
            label="Type"
            size="md"
            width="fit"
            options={PROPERTY_TYPE_OPTIONS}
            value={propertyType}
            onValueChange={(next) => {
              if (next) setPropertyType(next);
            }}
          />
          <div className="flex items-center gap-1.5 pb-1.5">
            <Switch
              size="sm"
              aria-label="Required"
              checked={isRequired}
              onCheckedChange={(checked) => setIsRequired(checked)}
            />
            <span className="text-11 text-tertiary">Required</span>
          </div>
          <Button
            variant="primary"
            size="md"
            stretch="auto"
            label="Create"
            onClick={() => void addProperty()}
            disabled={!propertyName.trim()}
          />
        </div>
      )}
      <div className="flex flex-col gap-2">
        {(issueType.properties ?? []).length === 0 && (
          <span className="text-13 text-tertiary">No custom properties yet.</span>
        )}
        {(issueType.properties ?? []).map((property) => (
          <PropertyRow
            key={property.id}
            property={property}
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            isAdmin={isAdmin}
            onChanged={onChanged}
          />
        ))}
      </div>
    </div>
  );
});

export const IssueTypesSettingsRoot = observer(function IssueTypesSettingsRoot(props: Props) {
  const { workspaceSlug, projectId, isAdmin } = props;
  // state
  const [newTypeName, setNewTypeName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isEnabling, setIsEnabling] = useState(false);
  // data
  const { issueTypes, isLoading, mutate } = useIssueTypes(workspaceSlug, projectId);
  // derived values
  const systemKeys = new Set((issueTypes ?? []).map((type) => type.system_key));
  const hasSystemTypes = systemKeys.has("task") && systemKeys.has("epic");

  const enableTypes = async () => {
    if (!isAdmin || isEnabling) return;
    setIsEnabling(true);
    try {
      await issueTypeService.enableIssueTypes(workspaceSlug, projectId);
      await mutate();
      setToast({
        type: "success",
        title: "Work item types enabled",
        message: "Task and Epic are now available in this project.",
      });
    } catch {
      setToast({ type: "error", title: "Error!", message: "Failed to enable work item types." });
    } finally {
      setIsEnabling(false);
    }
  };

  const createType = async () => {
    if (!newTypeName.trim() || isCreating) return;
    setIsCreating(true);
    try {
      await issueTypeService.createIssueType(workspaceSlug, projectId, { name: newTypeName.trim() });
      setNewTypeName("");
      await mutate();
    } catch {
      setToast({ type: "error", title: "Error!", message: "Failed to create the work item type." });
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-subtle pb-3">
        <div>
          <h3 className="text-18 font-medium">Work item types</h3>
          <p className="text-13 text-tertiary">
            Organize work with Task, Epic, and custom types. Epics are level 1 work items and appear in Work Items.
          </p>
        </div>
        {isAdmin && hasSystemTypes && (
          <div className="flex items-center gap-2">
            <div className="w-40">
              <InputGroup size="md">
                <Input
                  id="new-type-name"
                  size="md"
                  type="text"
                  aria-label="New work item type name"
                  value={newTypeName}
                  onChange={(e) => setNewTypeName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void createType();
                  }}
                  placeholder="e.g. Bug"
                />
              </InputGroup>
            </div>
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              icon={<Icon icon={AddOutline} />}
              label="Add type"
              onClick={() => void createType()}
              disabled={!newTypeName.trim()}
            />
          </div>
        )}
      </div>
      {!isLoading && !hasSystemTypes && (
        <div className="flex items-center justify-between gap-4 rounded-lg border border-subtle p-4">
          <div>
            <p className="text-14 font-medium">Work item types are not enabled</p>
            <p className="text-13 text-tertiary">
              Enable them to create Tasks and Epics from the shared Work Items views.
            </p>
          </div>
          {isAdmin && (
            <Button
              variant="primary"
              size="md"
              stretch="auto"
              label={isEnabling ? "Enabling…" : "Enable work item types"}
              onClick={() => void enableTypes()}
              disabled={isEnabling}
            />
          )}
        </div>
      )}
      {hasSystemTypes && (
        <WorkshopsCard
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isAdmin={isAdmin}
          onChanged={() => void mutate()}
        />
      )}
      {(issueTypes ?? []).map((issueType) => (
        <TypeCard
          key={issueType.id}
          issueType={issueType}
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          isAdmin={isAdmin}
          onChanged={() => void mutate()}
        />
      ))}
    </div>
  );
});
