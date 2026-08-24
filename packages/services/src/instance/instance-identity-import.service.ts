/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
// api service
import { APIService } from "../api.service";

export type TIdentityImportRow = {
  line: number;
  email: string;
  subject: string;
  action: "link" | "already-linked";
};

export type TIdentityImportError = {
  line: number;
  code: string;
  first_line?: number;
};

export type TIdentityImportReport = {
  provider: string;
  issuer: string;
  source: string;
  input_sha256: string;
  dry_run: boolean;
  row_count: number;
  imported_count: number;
  existing_count: number;
  errors: TIdentityImportError[];
};

export type TIdentityImportPreview = {
  valid: boolean;
  report: TIdentityImportReport;
  rows: TIdentityImportRow[];
  /** Present only when the file is valid; required to confirm it. */
  grant?: string;
};

/**
 * Federated identity import for the instance-admin console.
 *
 * The file is uploaded twice — once to preview, once to confirm — because the
 * server keeps nothing in between. The grant returned by the preview carries
 * the file's digest, so the confirmation can only apply the file that was
 * reviewed.
 *
 * Under /api/instances/ for the same reason as every other console call: the
 * session middleware selects the admin cookie by that substring.
 */
export class InstanceIdentityImportService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  private form(file: File, provider: string, issuer: string): FormData {
    const body = new FormData();
    body.append("file", file);
    body.append("provider", provider);
    body.append("issuer", issuer);
    return body;
  }

  private headers(csrfToken: string) {
    return { headers: { "X-CSRFTOKEN": csrfToken } };
  }

  async providers(): Promise<{ providers: string[] }> {
    return this.get("/api/instances/identity-import/")
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async preview(
    csrfToken: string,
    payload: { file: File; provider: string; issuer: string }
  ): Promise<TIdentityImportPreview> {
    return this.post(
      "/api/instances/identity-import/",
      this.form(payload.file, payload.provider, payload.issuer),
      this.headers(csrfToken)
    )
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async confirm(
    csrfToken: string,
    payload: { file: File; provider: string; issuer: string; grant: string; password: string }
  ): Promise<{ valid: boolean; report: TIdentityImportReport }> {
    const body = this.form(payload.file, payload.provider, payload.issuer);
    body.append("confirm", "true");
    body.append("grant", payload.grant);
    body.append("password", payload.password);

    return this.post("/api/instances/identity-import/", body, this.headers(csrfToken))
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
