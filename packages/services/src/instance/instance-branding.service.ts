/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
// api service
import { APIService } from "../api.service";

/**
 * The sign-in page logo.
 *
 * Only the image needs its own calls; the wording goes through the ordinary
 * configuration endpoint like every other setting.
 */
export type TBrandingImage = "logo" | "login-background";

export class InstanceBrandingService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private headers(csrfToken: string) {
    return { headers: { "X-CSRFTOKEN": csrfToken } };
  }

  async uploadImage(
    csrfToken: string,
    kind: TBrandingImage,
    file: File
  ): Promise<{ asset_id: string; asset_url: string }> {
    const body = new FormData();
    body.append("file", file);
    return this.post(`/api/instances/branding/images/${kind}/`, body, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async clearImage(csrfToken: string, kind: TBrandingImage): Promise<void> {
    return this.delete(`/api/instances/branding/images/${kind}/`, {}, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
