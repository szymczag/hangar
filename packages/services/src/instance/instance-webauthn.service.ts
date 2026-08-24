/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
// api service
import { APIService } from "../api.service";

export type TAdminWebAuthnCredential = {
  id: string;
  nickname: string;
  created_at: string;
  last_used_at: string | null;
  backup_eligible: boolean;
  disabled_at: string | null;
};

/**
 * Second factor for the instance-admin console.
 *
 * Every path lives under /api/instances/ because the session middleware selects
 * the admin cookie by that substring — a route elsewhere would operate on the
 * application session instead.
 */
export class InstanceWebAuthnService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private headers(csrfToken: string) {
    return { headers: { "X-CSRFTOKEN": csrfToken } };
  }

  async authenticationOptions(csrfToken: string): Promise<{ options: string }> {
    return this.post("/api/instances/admins/webauthn/authentication/options/", {}, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async verifyAuthentication(
    csrfToken: string,
    payload: { credential: unknown; challenge: string }
  ): Promise<{ redirect_url: string }> {
    return this.post("/api/instances/admins/webauthn/authentication/verify/", payload, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async registrationOptions(csrfToken: string): Promise<{ options: string; user_handle: string }> {
    return this.post("/api/instances/admins/webauthn/registration/options/", {}, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async verifyRegistration(
    csrfToken: string,
    payload: { credential: unknown; challenge: string; user_handle: string; nickname: string }
  ): Promise<{ redirect_url?: string; id?: string }> {
    return this.post("/api/instances/admins/webauthn/registration/verify/", payload, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async credentials(): Promise<TAdminWebAuthnCredential[]> {
    return this.get("/api/instances/admins/webauthn/credentials/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async removeCredential(id: string, csrfToken: string): Promise<void> {
    return this.delete(`/api/instances/admins/webauthn/credentials/${id}/`, {}, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
