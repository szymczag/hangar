/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

const MAX_LENGTH = 200;

const firstString = (value: unknown): string | undefined => {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (Array.isArray(value)) {
    for (const entry of value) {
      const message = firstString(entry);
      if (message) return message;
    }
  }
  return undefined;
};

/**
 * The reason the server gave, for a toast.
 *
 * Work item rejections arrive either as `{"detail": "..."}` or as DRF's field
 * errors, for example `{"parent_id": ["Epic work items cannot have a parent"]}`.
 * Without this the client reported "Error while updating work item" and dropped
 * the only sentence that explains what to do differently.
 */
export const getWorkItemErrorMessage = (error: unknown, fallback: string): string => {
  const payload = (error as { response?: { data?: unknown }; data?: unknown })?.response?.data ?? error;
  const direct = firstString(payload);
  if (direct) return direct.slice(0, MAX_LENGTH);

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    for (const key of ["detail", "error", "message", "non_field_errors"]) {
      const message = firstString(record[key]);
      if (message) return message.slice(0, MAX_LENGTH);
    }
    // Any remaining field error, so a new server-side rule still reaches the viewer.
    for (const value of Object.values(record)) {
      const message = firstString(value);
      if (message) return message.slice(0, MAX_LENGTH);
    }
  }

  return fallback;
};
