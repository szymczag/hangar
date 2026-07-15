/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";
import type { TImportJob, TImportJobList, TTodoistImportConfig, TTodoistImportPreview } from "@/plane-web/types/import";

export class ImportService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private async csrfToken(): Promise<string> {
    const response = await this.get("/auth/get-csrf-token/");
    const token = response.data?.csrf_token;
    if (!token) throw new Error("CSRF token not found");
    return token;
  }

  async previewTodoist(
    workspaceSlug: string,
    projectId: string,
    file: File,
    signal?: AbortSignal
  ): Promise<TTodoistImportPreview> {
    const data = new FormData();
    data.append("project_id", projectId);
    data.append("file", file);
    return this.post(`/api/workspaces/${workspaceSlug}/imports/todoist/preview/`, data, { signal })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async startTodoist(
    workspaceSlug: string,
    projectId: string,
    file: File,
    previewDigest: string,
    config: TTodoistImportConfig,
    retryJobId?: string | null
  ): Promise<TImportJob> {
    const csrfToken = await this.csrfToken();
    const data = new FormData();
    data.append("project_id", projectId);
    data.append("file", file);
    data.append("preview_digest", previewDigest);
    data.append("config", JSON.stringify(config));
    if (retryJobId) data.append("retry_job_id", retryJobId);
    return this.post(`/api/workspaces/${workspaceSlug}/imports/todoist/`, data, {
      headers: { "X-CSRFTOKEN": csrfToken },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async list(workspaceSlug: string, cursor = "20:0:0"): Promise<TImportJobList> {
    return this.get(`/api/workspaces/${workspaceSlug}/imports/?cursor=${encodeURIComponent(cursor)}&per_page=20`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async cancel(workspaceSlug: string, jobId: string): Promise<TImportJob> {
    const csrfToken = await this.csrfToken();
    return this.post(`/api/workspaces/${workspaceSlug}/imports/${jobId}/cancel/`, undefined, {
      headers: { "X-CSRFTOKEN": csrfToken },
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  reportUrl(workspaceSlug: string, jobId: string): string {
    return `${API_BASE_URL}/api/workspaces/${workspaceSlug}/imports/${jobId}/report/`;
  }
}

export const importService = new ImportService();
