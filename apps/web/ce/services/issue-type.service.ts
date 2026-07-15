/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TIssuePropertyValues } from "@plane/types";
import { APIService } from "@/services/api.service";
import type { TIssuePropertyExt, TIssueTypeExt } from "@/plane-web/types/issue-types";

export class IssueTypeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getIssueTypes(workspaceSlug: string, projectId: string, includeProperties = true): Promise<TIssueTypeExt[]> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-types/`, {
      params: includeProperties ? { include: "properties" } : {},
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async enableIssueTypes(workspaceSlug: string, projectId: string): Promise<TIssueTypeExt[]> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-types/enable/`, {})
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createIssueType(workspaceSlug: string, projectId: string, data: Partial<TIssueTypeExt>) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-types/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateIssueType(workspaceSlug: string, projectId: string, typeId: string, data: Partial<TIssueTypeExt>) {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-types/${typeId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createProperty(workspaceSlug: string, projectId: string, typeId: string, data: Partial<TIssuePropertyExt>) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issue-types/${typeId}/properties/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createOption(workspaceSlug: string, projectId: string, propertyId: string, data: { name: string }) {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/properties/${propertyId}/options/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getPropertyValues(workspaceSlug: string, projectId: string, issueId: string): Promise<TIssuePropertyValues> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/property-values/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updatePropertyValues(
    workspaceSlug: string,
    projectId: string,
    issueId: string,
    values: TIssuePropertyValues
  ): Promise<void> {
    return this.post(
      `/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/property-values/`,
      values
    )
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

export const issueTypeService = new IssueTypeService();
