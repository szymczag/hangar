/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
// api service
import { APIService } from "../api.service";

export type TUserOpenPGPState = {
  user_id: string;
  email: string;
  is_locked: boolean;
  locked_at: string | null;
  note: string;
  active_key: {
    primary_fingerprint: string;
    encryption_algorithm: string;
    key_expires_at: string | null;
    verified_at: string | null;
  } | null;
};

/**
 * Administrator control over a person's encryption key.
 *
 * Setting someone's key decides who can read their mail, so every call here is
 * recorded server-side and the account owner is emailed. Under /api/instances/
 * so it uses the console session and its second factor.
 */
export class InstanceOpenPGPService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private headers(csrfToken: string) {
    return { headers: { "X-CSRFTOKEN": csrfToken } };
  }

  async state(userId: string): Promise<TUserOpenPGPState> {
    return this.get(`/api/instances/users/${userId}/openpgp/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async setKey(
    csrfToken: string,
    userId: string,
    payload: { certificate: string; note?: string }
  ): Promise<TUserOpenPGPState> {
    return this.post(`/api/instances/users/${userId}/openpgp/`, payload, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async setLock(
    csrfToken: string,
    userId: string,
    payload: { is_locked: boolean; note?: string }
  ): Promise<TUserOpenPGPState> {
    return this.patch(`/api/instances/users/${userId}/openpgp/`, payload, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
