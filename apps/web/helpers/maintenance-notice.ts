/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TMaintenanceSeverity = "info" | "warning" | "critical";

export type TMaintenanceNotice = {
  severity: TMaintenanceSeverity;
  message: string;
  starts_at: string | null;
  ends_at: string | null;
  /** Digest of the wording and window. Dismissal keys off this. */
  fingerprint: string;
};

const LAST_SEEN_KEY = "hangar-maintenance-notice";
const DISMISSED_KEY = "hangar-maintenance-dismissed";

const SEVERITIES = new Set<string>(["info", "warning", "critical"]);

/** A usable date, or not. Both bounds are optional and either may be malformed. */
const isUsableDate = (date: Date | null): date is Date => date !== null && !Number.isNaN(date.getTime());

/** Narrow an untrusted parsed value to a notice, or `null`. */
export const asMaintenanceNotice = (value: unknown): TMaintenanceNotice | null => {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  if (typeof candidate.message !== "string" || !candidate.message.trim()) return null;
  if (typeof candidate.fingerprint !== "string" || !candidate.fingerprint) return null;
  if (typeof candidate.severity !== "string" || !SEVERITIES.has(candidate.severity)) return null;
  return {
    severity: candidate.severity as TMaintenanceSeverity,
    message: candidate.message,
    starts_at: typeof candidate.starts_at === "string" ? candidate.starts_at : null,
    ends_at: typeof candidate.ends_at === "string" ? candidate.ends_at : null,
    fingerprint: candidate.fingerprint,
  };
};

/**
 * Keep the last notice, so the bar survives the API being unreachable.
 *
 * Which is exactly when it matters: an outage severe enough to take the API
 * down is the outage worth announcing, and at that point nothing can be asked.
 */
export const rememberMaintenanceNotice = (notice: TMaintenanceNotice | null): void => {
  if (typeof window === "undefined") return;
  try {
    if (notice) window.localStorage.setItem(LAST_SEEN_KEY, JSON.stringify(notice));
    else window.localStorage.removeItem(LAST_SEEN_KEY);
  } catch {
    // A quota or a private window. The bar simply will not persist.
  }
};

export const recalledMaintenanceNotice = (): TMaintenanceNotice | null => {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(LAST_SEEN_KEY);
    return stored ? asMaintenanceNotice(JSON.parse(stored)) : null;
  } catch {
    return null;
  }
};

export const dismissMaintenanceNotice = (fingerprint: string): void => {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(DISMISSED_KEY, fingerprint);
  } catch {
    // Then it reappears on the next load, which is the safe direction: a
    // notice shown twice is a nuisance, one silently hidden is a failure.
  }
};

export const dismissedMaintenanceFingerprint = (): string | null => {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(DISMISSED_KEY);
  } catch {
    return null;
  }
};

/**
 * The window as local times, or an empty string when there is nothing to say.
 *
 * Real times rather than a countdown: an operator announcing a window does not
 * know it to the second, and a ticking clock claims a precision they do not have.
 */
export const formatMaintenanceWindow = (notice: TMaintenanceNotice, locale?: string): string => {
  const start = notice.starts_at ? new Date(notice.starts_at) : null;
  const end = notice.ends_at ? new Date(notice.ends_at) : null;
  const time = (date: Date) => date.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  const dayAndTime = (date: Date) =>
    date.toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

  if (isUsableDate(start) && isUsableDate(end)) {
    const sameDay = start.toDateString() === end.toDateString();
    return sameDay ? `${dayAndTime(start)} – ${time(end)}` : `${dayAndTime(start)} – ${dayAndTime(end)}`;
  }
  if (isUsableDate(start)) return `From ${dayAndTime(start)}`;
  if (isUsableDate(end)) return `Until ${dayAndTime(end)}`;
  return "";
};
