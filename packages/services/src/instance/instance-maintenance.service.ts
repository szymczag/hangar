/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
// api service
import { APIService } from "../api.service";

export type TMaintenanceSeverity = "info" | "warning" | "critical";

export type TMaintenanceNoticePublic = {
  severity: TMaintenanceSeverity;
  message: string;
  starts_at: string | null;
  ends_at: string | null;
  fingerprint: string;
};

export type TMaintenanceNoticeAdmin = {
  is_enabled: boolean;
  message: string;
  severity: TMaintenanceSeverity;
  starts_at: string | null;
  ends_at: string | null;
  show_on_sign_in: boolean;
  is_active: boolean;
  fingerprint: string | null;
};

/**
 * The instance-wide maintenance notice.
 *
 * The two paths are not interchangeable. `/api/maintenance/` is the anonymous
 * read, deliberately outside `/api/instances/` because the session middleware
 * switches to the admin cookie on any path containing "instances" -- which
 * would make every signed-in reader look anonymous. The console path keeps that
 * prefix precisely because it wants the admin cookie.
 */
export class InstanceMaintenanceService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async retrieve(): Promise<{ notice: TMaintenanceNoticePublic | null }> {
    return this.get("/api/maintenance/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async retrieveForAdmin(): Promise<TMaintenanceNoticeAdmin> {
    return this.get("/api/instances/maintenance/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(csrfToken: string, payload: Partial<TMaintenanceNoticeAdmin>): Promise<TMaintenanceNoticeAdmin> {
    return this.patch("/api/instances/maintenance/", payload, { headers: { "X-CSRFTOKEN": csrfToken } })
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
