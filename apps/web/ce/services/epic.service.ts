/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TIssue } from "@plane/types";
import { APIService } from "@/services/api.service";

export type TEpicSettings = {
  is_epic_enabled: boolean;
};

export class EpicService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getSettings(workspaceSlug: string, projectId: string): Promise<TEpicSettings> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/epic-settings/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateSettings(workspaceSlug: string, projectId: string, data: TEpicSettings): Promise<TEpicSettings> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/epic-settings/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createEpic(workspaceSlug: string, projectId: string, data: Partial<TIssue>): Promise<TIssue> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/epics/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateEpic(workspaceSlug: string, projectId: string, epicId: string, data: Partial<TIssue>): Promise<TIssue> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/epics/${epicId}/`, data)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

export const epicService = new EpicService();
