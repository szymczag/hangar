/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// types
import { API_BASE_URL } from "@plane/constants";
import type { IInstanceInfo } from "@plane/types";
// helpers
// services
import { APIService } from "@/services/api.service";

export class InstanceService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async requestCSRFToken(): Promise<{ csrf_token: string }> {
    return this.get("/auth/get-csrf-token/")
      .then((response) => response.data)
      .catch((error) => {
        throw error;
      });
  }

  async getInstanceInfo(): Promise<IInstanceInfo> {
    return this.get("/api/instances/")
      .then((response) => response.data)
      .catch((error) => {
        throw error;
      });
  }

  /**
   * The full instance configuration, for a signed-in user. /api/instances/ answers
   * a caller without an admin session with only what the sign-in pages need.
   */
  async getMemberInstanceInfo(): Promise<IInstanceInfo> {
    return this.get("/api/users/me/instance-config/")
      .then((response) => response.data)
      .catch((error) => {
        throw error;
      });
  }
}
