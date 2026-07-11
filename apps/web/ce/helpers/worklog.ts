/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Mirrors the server-side cap (24h per entry).
export const MAX_WORKLOG_MINUTES = 24 * 60;

export function formatWorklogDuration(minutes: number): string {
  const total = Math.max(0, Math.floor(minutes || 0));
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  if (hours && rest) return `${hours}h ${rest}m`;
  if (hours) return `${hours}h`;
  return `${rest}m`;
}

/**
 * Parses a human duration into minutes.
 * Accepts "2h 30m", "2h30m", "2h", "30m", "1.5h" and plain minutes ("90").
 * Returns null when the input cannot be parsed or resolves to zero.
 */
export function parseWorklogDuration(input: string): number | null {
  const value = input.trim().toLowerCase();
  if (!value) return null;
  if (/^\d+$/.test(value)) {
    const minutes = parseInt(value, 10);
    return minutes > 0 ? minutes : null;
  }
  const match = value.match(/^(?:(\d+(?:[.,]\d+)?)\s*h)?\s*(?:(\d+)\s*m(?:in)?s?)?$/);
  if (!match || (match[1] === undefined && match[2] === undefined)) return null;
  const hours = match[1] ? parseFloat(match[1].replace(",", ".")) : 0;
  const mins = match[2] ? parseInt(match[2], 10) : 0;
  const minutes = Math.round(hours * 60 + mins);
  return minutes > 0 ? minutes : null;
}
