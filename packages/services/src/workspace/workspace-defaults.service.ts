/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
// api service
import { APIService } from "../api.service";

export type TWorkspaceHomeDefault = {
  key: string;
  is_enabled: boolean;
  sort_order: number;
  config: Record<string, unknown>;
};

export type TWorkspaceHomeDefaults = {
  defaults: TWorkspaceHomeDefault[];
  version: number;
  available_keys: string[];
  members_updated?: number;
};

export type TWorkspaceSharedLink = {
  id: string;
  title: string;
  url: string;
  metadata: Record<string, unknown>;
  sort_order: number;
  /** Hidden by the person asking, not by the workspace. */
  is_hidden: boolean;
};

/**
 * The home page a workspace gives its people.
 *
 * Defaults are seeded per person and then theirs; shared links stay one list
 * everybody reads, which is what makes fixing a URL or retiring a dead service
 * reach everyone instead of nobody.
 */
export class WorkspaceDefaultsService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async retrieveHomeDefaults(slug: string): Promise<TWorkspaceHomeDefaults> {
    return this.get(`/api/workspaces/${slug}/home-defaults/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateHomeDefaults(
    slug: string,
    defaults: TWorkspaceHomeDefault[],
    applyToEveryone: boolean
  ): Promise<TWorkspaceHomeDefaults> {
    return this.patch(`/api/workspaces/${slug}/home-defaults/`, {
      defaults,
      apply_to_everyone: applyToEveryone,
    })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async listSharedLinks(slug: string): Promise<TWorkspaceSharedLink[]> {
    return this.get(`/api/workspaces/${slug}/shared-links/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async createSharedLink(slug: string, payload: { title: string; url: string }): Promise<TWorkspaceSharedLink> {
    return this.post(`/api/workspaces/${slug}/shared-links/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateSharedLink(
    slug: string,
    linkId: string,
    payload: Partial<{ title: string; url: string; sort_order: number }>
  ): Promise<TWorkspaceSharedLink> {
    return this.patch(`/api/workspaces/${slug}/shared-links/${linkId}/`, payload)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async deleteSharedLink(slug: string, linkId: string): Promise<void> {
    return this.delete(`/api/workspaces/${slug}/shared-links/${linkId}/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  /** Hiding is the member's own business, so it is open to every role. */
  async setSharedLinkHidden(slug: string, linkId: string, hidden: boolean): Promise<void> {
    const path = `/api/workspaces/${slug}/shared-links/${linkId}/hide/`;
    const request = hidden ? this.post(path, {}) : this.delete(path);
    return request
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
