/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The reason a configuration write was refused, as the server stated it.
 *
 * Every refusal from the configuration endpoint explains something the
 * administrator has to act on — the instance reads its settings from the
 * environment, the key is deployment-owned, the value is not valid, the
 * instance stores nothing under that name. Replacing all of them with "Failed
 * to save configuration" and pushing the real text to the browser console
 * turns a diagnosable answer into a mystery, since the console is the last
 * place someone administering an instance thinks to look.
 */
export function configurationErrorMessage(error: unknown, fallback = "Failed to save configuration"): string {
  const reported = (error as { error?: unknown })?.error;
  if (typeof reported === "string" && reported.trim()) return reported;

  // Field-level validation answers arrive as { detail } or { <field>: [...] }.
  const detail = (error as { detail?: unknown })?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;

  return fallback;
}
