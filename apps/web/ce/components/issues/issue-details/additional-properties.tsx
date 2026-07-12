/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): renders custom-property widgets in the work item
// sidebar/peek. Values load from the bundle endpoint and save per property
// on change.

import React, { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// plane imports
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIssuePropertyValues } from "@plane/types";
// plane web
import { PropertyValueInput } from "@/plane-web/components/issues/issue-properties/property-value-input";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";
import { issueTypeService } from "@/plane-web/services/issue-type.service";

export type TWorkItemAdditionalSidebarProperties = {
  workItemId: string;
  workItemTypeId: string | null;
  projectId: string;
  workspaceSlug: string;
  isEditable: boolean;
  isPeekView?: boolean;
};

export const WorkItemAdditionalSidebarProperties = observer(function WorkItemAdditionalSidebarProperties(
  props: TWorkItemAdditionalSidebarProperties
) {
  const { workItemId, workItemTypeId, projectId, workspaceSlug, isEditable } = props;
  // data
  const { activeProperties } = useIssueTypes(workspaceSlug, projectId);
  const { data: values, mutate } = useSWR<TIssuePropertyValues>(
    workItemId ? `ISSUE_PROPERTY_VALUES_${workItemId}` : null,
    () => issueTypeService.getPropertyValues(workspaceSlug, projectId, workItemId),
    { revalidateOnFocus: false }
  );
  const [isSaving, setIsSaving] = useState(false);

  const properties = activeProperties(workItemTypeId);
  if (!workItemTypeId || properties.length === 0) return null;

  const handleChange = async (propertyId: string, next: string[]) => {
    if (!values || isSaving) return;
    const previous = values;
    const optimistic = { ...previous, [propertyId]: next };
    setIsSaving(true);
    await mutate(optimistic, { revalidate: false });
    try {
      await issueTypeService.updatePropertyValues(workspaceSlug, projectId, workItemId, optimistic);
    } catch (error) {
      console.error(error);
      await mutate(previous, { revalidate: false });
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to update the property." });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 py-2">
      {properties.map((property) => (
        <div key={property.id} className="flex min-h-8 w-full items-center gap-3">
          <div className="flex w-2/5 flex-shrink-0 items-center gap-1 text-14 text-tertiary">
            {property.display_name}
            {property.is_required && <span className="text-danger-primary">*</span>}
          </div>
          <div className="w-3/5">
            <PropertyValueInput
              property={property}
              values={((values ?? {})[property.id] as string[] | undefined) ?? []}
              onChange={(next) => void handleChange(property.id, next)}
              projectId={projectId}
              disabled={!isEditable || !values || isSaving}
            />
          </div>
        </div>
      ))}
    </div>
  );
});
