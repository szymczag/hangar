/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): implements the custom-property handlers upstream ships
// as no-ops. Property definitions are fetched per project; values are held in
// modal state and written through the bundle endpoint after the work item is
// created or updated.

import React, { useCallback, useRef, useState } from "react";
import { observer } from "mobx-react";
// plane imports
import type { ISearchIssueResponse, TIssue, TIssuePropertyValueErrors, TIssuePropertyValues } from "@plane/types";
// components
import type {
  TActiveAdditionalPropertiesProps,
  TCreateUpdatePropertyValuesProps,
  THandleProjectEntitiesFetchProps,
  TPropertyValuesValidationProps,
} from "@/components/issues/issue-modal/context";
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useUser } from "@/hooks/store/user/user-user";
// plane web
import { issueTypeService } from "@/plane-web/services/issue-type.service";
import type { TIssueTypeExt } from "@/plane-web/types/issue-types";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds } = props;
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  const [issuePropertyValues, setIssuePropertyValues] = useState<TIssuePropertyValues>({});
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});
  // Per-project issue type definitions, fetched on project change. A ref is
  // enough — consumers re-render through the state setters above.
  const issueTypesByProject = useRef<Record<string, TIssueTypeExt[]>>({});
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  const getProjectTypes = useCallback(
    (projectId: string | null | undefined) => (projectId ? (issueTypesByProject.current[projectId] ?? []) : []),
    []
  );

  const getActiveProperties = useCallback(
    (projectId: string | null | undefined, typeId: string | null | undefined) => {
      const type = getProjectTypes(projectId).find((item) => item.id === typeId);
      return (type?.properties ?? []).filter((property) => property.is_active);
    },
    [getProjectTypes]
  );

  const handleProjectEntitiesFetch = useCallback(
    async ({ workItemProjectId, workspaceSlug }: THandleProjectEntitiesFetchProps) => {
      if (!workItemProjectId || issueTypesByProject.current[workItemProjectId]) return;
      try {
        issueTypesByProject.current[workItemProjectId] = await issueTypeService.getIssueTypes(
          workspaceSlug,
          workItemProjectId
        );
      } catch {
        issueTypesByProject.current[workItemProjectId] = [];
      }
    },
    []
  );

  const getIssueTypeIdOnProjectChange = useCallback(
    (projectId: string) => {
      const types = getProjectTypes(projectId).filter((type) => !type.is_epic && type.is_active);
      return types.find((type) => type.is_default)?.id ?? null;
    },
    [getProjectTypes]
  );

  const getActiveAdditionalPropertiesLength = useCallback(
    ({ projectId, watch }: TActiveAdditionalPropertiesProps) => getActiveProperties(projectId, watch("type_id")).length,
    [getActiveProperties]
  );

  const handlePropertyValuesValidation = useCallback(
    ({ projectId, watch }: TPropertyValuesValidationProps) => {
      const properties = getActiveProperties(projectId, watch("type_id"));
      const errors: TIssuePropertyValueErrors = {};
      for (const property of properties) {
        const values = (issuePropertyValues[property.id] as string[] | undefined) ?? [];
        if (property.is_required && values.filter(Boolean).length === 0) {
          errors[property.id] = "REQUIRED";
        }
      }
      setIssuePropertyValueErrors(errors);
      return Object.keys(errors).length === 0;
    },
    [getActiveProperties, issuePropertyValues]
  );

  const handleCreateUpdatePropertyValues = useCallback(
    async ({ issueId, projectId, workspaceSlug, issueTypeId }: TCreateUpdatePropertyValuesProps) => {
      const properties = getActiveProperties(projectId, issueTypeId);
      if (properties.length === 0) return;
      const payload: TIssuePropertyValues = {};
      for (const property of properties) {
        if (property.id in issuePropertyValues) payload[property.id] = issuePropertyValues[property.id];
      }
      if (Object.keys(payload).length === 0) return;
      await issueTypeService.updatePropertyValues(workspaceSlug, projectId, issueId, payload);
      setIssuePropertyValues({});
    },
    [getActiveProperties, issuePropertyValues]
  );

  return (
    <IssueModalContext.Provider
      value={{
        allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
        workItemTemplateId: null,
        setWorkItemTemplateId: () => {},
        isApplyingTemplate: false,
        setIsApplyingTemplate: () => {},
        selectedParentIssue,
        setSelectedParentIssue,
        issuePropertyValues,
        setIssuePropertyValues,
        issuePropertyValueErrors,
        setIssuePropertyValueErrors,
        getIssueTypeIdOnProjectChange,
        getActiveAdditionalPropertiesLength,
        handlePropertyValuesValidation,
        handleCreateUpdatePropertyValues,
        handleProjectEntitiesFetch,
        handleTemplateChange: () => Promise.resolve(),
        handleConvert: () => Promise.resolve(),
        handleCreateSubWorkItem: () => Promise.resolve(),
      }}
    >
      {children}
    </IssueModalContext.Provider>
  );
});
