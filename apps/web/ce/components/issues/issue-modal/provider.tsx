/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): implements the custom-property handlers upstream ships
// as no-ops. Property definitions are fetched per project; values are held in
// modal state and written through the bundle endpoint after the work item is
// created or updated.

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { mutate } from "swr";
// plane imports
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { ISearchIssueResponse, TIssue, TIssuePropertyValueErrors, TIssuePropertyValues } from "@plane/types";
// components
import type {
  TActiveAdditionalPropertiesProps,
  TCreateUpdatePropertyValuesProps,
  THandleProjectEntitiesFetchProps,
  TIssueModalContext,
  TPropertyValuesValidationProps,
} from "@/components/issues/issue-modal/context";
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useUser } from "@/hooks/store/user/user-user";
// plane web
import { getIssueTypesKey } from "@/plane-web/hooks/use-issue-types";
import { issueTypeService } from "@/plane-web/services/issue-type.service";
import type { TIssueTypeExt } from "@/plane-web/types/issue-types";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds, dataForPreload } = props;
  const { workspaceSlug: routeWorkspaceSlug } = useParams();
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  const [issuePropertyValues, setIssuePropertyValues] = useState<TIssuePropertyValues>({});
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});
  // The ref provides synchronous reads after an awaited fetch; the state map
  // makes schema-dependent consumers re-render. SWR remains the shared cache
  // used by the rendered inputs.
  const issueTypesByProjectRef = useRef<Record<string, TIssueTypeExt[]>>({});
  const [, setIssueTypesByProject] = useState<Record<string, TIssueTypeExt[]>>({});
  const schemaStatusByProject = useRef<Record<string, "loading" | "ready" | "error">>({});
  const schemaRequestsByProject = useRef<Record<string, Promise<void>>>({});
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  const getProjectTypes = useCallback(
    (projectId: string | null | undefined) => (projectId ? (issueTypesByProjectRef.current[projectId] ?? []) : []),
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
      if (!workItemProjectId || schemaStatusByProject.current[workItemProjectId] === "ready") return;
      const pendingRequest = schemaRequestsByProject.current[workItemProjectId];
      if (pendingRequest) return pendingRequest;

      schemaStatusByProject.current[workItemProjectId] = "loading";
      const request = (async () => {
        try {
          const types = await mutate<TIssueTypeExt[]>(
            getIssueTypesKey(workspaceSlug, workItemProjectId),
            issueTypeService.getIssueTypes(workspaceSlug, workItemProjectId),
            { populateCache: true, revalidate: false }
          );
          if (!types) throw new Error("Issue type schema returned no data");
          issueTypesByProjectRef.current[workItemProjectId] = types;
          schemaStatusByProject.current[workItemProjectId] = "ready";
          setIssueTypesByProject((current) => ({ ...current, [workItemProjectId]: types }));
        } catch (error) {
          schemaStatusByProject.current[workItemProjectId] = "error";
          throw error;
        } finally {
          delete schemaRequestsByProject.current[workItemProjectId];
        }
      })();
      schemaRequestsByProject.current[workItemProjectId] = request;
      return request;
    },
    []
  );

  useEffect(() => {
    const workspaceSlug = routeWorkspaceSlug?.toString();
    const issueId = dataForPreload?.id;
    const projectId = dataForPreload?.project_id;
    let cancelled = false;

    if (!workspaceSlug || !issueId || !projectId) {
      setIssuePropertyValues({});
      return;
    }

    const preloadPropertyValues = async () => {
      try {
        const [, values] = await Promise.all([
          handleProjectEntitiesFetch({
            workspaceSlug,
            workItemProjectId: projectId,
            workItemTypeId: dataForPreload.type_id ?? undefined,
          }),
          issueTypeService.getPropertyValues(workspaceSlug, projectId, issueId),
        ]);
        if (!cancelled) setIssuePropertyValues(values);
      } catch {
        if (!cancelled) setIssuePropertyValues({});
      }
    };

    void preloadPropertyValues();
    return () => {
      cancelled = true;
    };
  }, [
    dataForPreload?.id,
    dataForPreload?.project_id,
    dataForPreload?.type_id,
    handleProjectEntitiesFetch,
    routeWorkspaceSlug,
  ]);

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
      if (!projectId || schemaStatusByProject.current[projectId] !== "ready") {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: "Unable to validate work item properties",
          message: "The work item type schema is not available yet. Retry after it finishes loading.",
        });
        return false;
      }
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
      await handleProjectEntitiesFetch({
        workspaceSlug,
        workItemProjectId: projectId,
        workItemTypeId: issueTypeId ?? undefined,
      });
      const properties = getActiveProperties(projectId, issueTypeId);
      const payload: TIssuePropertyValues = {};
      for (const property of properties) {
        payload[property.id] = issuePropertyValues[property.id] ?? [];
      }
      await issueTypeService.updatePropertyValues(workspaceSlug, projectId, issueId, payload);
      setIssuePropertyValues({});
    },
    [getActiveProperties, handleProjectEntitiesFetch, issuePropertyValues]
  );

  const contextValue = useMemo<TIssueModalContext>(
    () => ({
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
    }),
    [
      allowedProjectIds,
      getActiveAdditionalPropertiesLength,
      getIssueTypeIdOnProjectChange,
      handleCreateUpdatePropertyValues,
      handleProjectEntitiesFetch,
      handlePropertyValuesValidation,
      issuePropertyValueErrors,
      issuePropertyValues,
      projectIdsWithCreatePermissions,
      selectedParentIssue,
    ]
  );

  return <IssueModalContext.Provider value={contextValue}>{children}</IssueModalContext.Provider>;
});
