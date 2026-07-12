/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): renders custom-property inputs for the selected work
// item type inside the create/update modal. Values live in the issue-modal
// context and are persisted by handleCreateUpdatePropertyValues after the
// work item is saved.

import { useEffect, useRef } from "react";
import { observer } from "mobx-react";
import { useFormContext } from "react-hook-form";
// plane imports
import type { TIssue, TIssuePropertyValues } from "@plane/types";
// hooks
import { useIssueModal } from "@/hooks/context/use-issue-modal";
// plane web
import { PropertyValueInput } from "@/plane-web/components/issues/issue-properties/property-value-input";
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";

export type TWorkItemModalAdditionalPropertiesProps = {
  isDraft?: boolean;
  projectId: string | null;
  workItemId: string | undefined;
  workspaceSlug: string;
};

export const WorkItemModalAdditionalProperties = observer(function WorkItemModalAdditionalProperties(
  props: TWorkItemModalAdditionalPropertiesProps
) {
  const { projectId, workspaceSlug } = props;
  // form context (the modal form is wrapped in a FormProvider)
  const { watch } = useFormContext<TIssue>();
  const typeId = watch("type_id");
  // context + data
  const { issuePropertyValues, setIssuePropertyValues, issuePropertyValueErrors, setIssuePropertyValueErrors } =
    useIssueModal();
  const { activeProperties } = useIssueTypes(workspaceSlug, projectId);
  const previousTypeId = useRef(typeId);

  useEffect(() => {
    if (previousTypeId.current && previousTypeId.current !== typeId) {
      setIssuePropertyValues({});
      setIssuePropertyValueErrors({});
    }
    previousTypeId.current = typeId;
  }, [setIssuePropertyValueErrors, setIssuePropertyValues, typeId]);

  if (!projectId || !typeId) return null;
  const properties = activeProperties(typeId);
  if (properties.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-3 py-3 md:grid-cols-2">
      {properties.map((property) => (
        <div key={property.id} className="flex flex-col gap-1">
          <span className="text-13 text-tertiary">
            {property.display_name}
            {property.is_required && <span className="text-danger-primary"> *</span>}
          </span>
          <PropertyValueInput
            property={property}
            values={(issuePropertyValues[property.id] as string[] | undefined) ?? []}
            onChange={(values) =>
              setIssuePropertyValues((prev: TIssuePropertyValues) => ({ ...prev, [property.id]: values }))
            }
            projectId={projectId}
            hasError={Boolean(issuePropertyValueErrors[property.id])}
          />
          {Boolean(issuePropertyValueErrors[property.id]) && (
            <span className="text-11 text-danger-primary">{property.display_name} is required</span>
          )}
        </div>
      ))}
    </div>
  );
});
