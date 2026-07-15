/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Management UI for a project's custom work item types and their properties.

import { useState } from "react";
import { observer } from "mobx-react";
// icons
import { Plus, Shapes } from "lucide-react";
// plane imports
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { CustomSelect, Input, ToggleSwitch } from "@plane/ui";
// plane web
import { issueTypeService } from "@/plane-web/services/issue-type.service";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import type { TIssuePropertyExt, TIssuePropertyType, TIssueTypeExt } from "@/plane-web/types/issue-types";

const PROPERTY_TYPE_OPTIONS: { key: TIssuePropertyType; label: string }[] = [
  { key: "text", label: "Text" },
  { key: "number", label: "Number" },
  { key: "date", label: "Date" },
  { key: "boolean", label: "Boolean" },
  { key: "select", label: "Select" },
  { key: "multi_select", label: "Multi select" },
  { key: "member", label: "Member" },
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
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to add the option." });
    }
  };

  return (
    <div className="flex flex-col gap-1 rounded-md border border-subtle px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-14">
          <span className="font-medium">{property.display_name}</span>
          <span className="rounded-sm bg-layer-1 px-1.5 py-0.5 text-11 text-tertiary">
            {PROPERTY_TYPE_OPTIONS.find((option) => option.key === property.property_type)?.label}
          </span>
          {property.is_required && <span className="text-11 text-danger-primary">required</span>}
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
              <Input
                id={`option-${property.id}`}
                type="text"
                value={optionName}
                onChange={(e) => setOptionName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void addOption();
                }}
                placeholder="Add option"
                className="h-6 w-32 text-11"
              />
            </div>
          )}
        </div>
      )}
    </div>
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
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to create the property." });
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-subtle p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shapes className="h-5 w-5 text-tertiary" />
          <span className="text-16 font-medium">{issueType.name}</span>
          {issueType.is_default && <span className="text-11 text-tertiary">default</span>}
          {issueType.system_key && (
            <span className="rounded-sm bg-layer-1 px-1.5 py-0.5 text-11 text-tertiary">
              {issueType.system_key === "epic" ? "level 1" : "level 0"}
            </span>
          )}
        </div>
        {isAdmin && (
          <Button variant="secondary" size="sm" onClick={() => setIsAddingProperty((prev) => !prev)}>
            <Plus className="h-3.5 w-3.5" />
            Add property
          </Button>
        )}
      </div>
      {isAddingProperty && (
        <div className="flex flex-wrap items-end gap-2 rounded-md bg-layer-1 p-3">
          <div className="flex flex-col gap-1">
            <span className="text-11 text-tertiary">Name</span>
            <Input
              id={`new-property-${issueType.id}`}
              type="text"
              value={propertyName}
              onChange={(e) => setPropertyName(e.target.value)}
              placeholder="Severity"
              className="h-7 w-40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-11 text-tertiary">Type</span>
            <CustomSelect
              value={propertyType}
              onChange={(next: TIssuePropertyType) => setPropertyType(next)}
              label={PROPERTY_TYPE_OPTIONS.find((option) => option.key === propertyType)?.label}
              buttonClassName="h-7"
            >
              {PROPERTY_TYPE_OPTIONS.map((option) => (
                <CustomSelect.Option key={option.key} value={option.key}>
                  {option.label}
                </CustomSelect.Option>
              ))}
            </CustomSelect>
          </div>
          <div className="flex items-center gap-1.5 pb-1">
            <ToggleSwitch value={isRequired} onChange={() => setIsRequired((prev) => !prev)} size="sm" />
            <span className="text-11 text-tertiary">Required</span>
          </div>
          <Button variant="primary" size="sm" onClick={() => void addProperty()} disabled={!propertyName.trim()}>
            Create
          </Button>
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
  const hasSystemTypes = (issueTypes ?? []).some((type) => type.system_key === "task" || type.system_key === "epic");

  const enableTypes = async () => {
    if (!isAdmin || isEnabling) return;
    setIsEnabling(true);
    try {
      await issueTypeService.enableIssueTypes(workspaceSlug, projectId);
      await mutate();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Work item types enabled",
        message: "Task and Epic are now available in this project.",
      });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to enable work item types." });
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
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to create the work item type." });
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
            <Input
              id="new-type-name"
              type="text"
              value={newTypeName}
              onChange={(e) => setNewTypeName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void createType();
              }}
              placeholder="e.g. Bug"
              className="h-7 w-40"
            />
            <Button variant="primary" size="sm" onClick={() => void createType()} disabled={!newTypeName.trim()}>
              <Plus className="h-3.5 w-3.5" />
              Add type
            </Button>
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
            <Button variant="primary" size="sm" onClick={() => void enableTypes()} disabled={isEnabling}>
              {isEnabling ? "Enabling…" : "Enable work item types"}
            </Button>
          )}
        </div>
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
