/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IInstanceConfig } from "@plane/types";

const STORAGE_KEY = "hangar-failure-page-branding";

export type TFailurePageBranding = {
  supportText: string;
  showExternalLinks: boolean;
};

const EMPTY: TFailurePageBranding = { supportText: "", showExternalLinks: false };

/**
 * Remember what the failure pages should say, while the instance can still say it.
 *
 * Those pages render precisely when `/api/instances/` could not be reached, so
 * they cannot ask. Without this the only options are a value compiled into the
 * bundle — which an operator cannot change without a rebuild — or upstream's
 * wording, which invites a company's staff to file a public bug report at the
 * moment their tools stop working.
 *
 * So the answer is kept from the last time it was available. Anyone who has
 * opened the application before has it; a first-time visitor arriving while the
 * instance is down gets the neutral wording and no links, which is the right
 * thing to show someone the instance knows nothing about.
 */
export const rememberFailurePageBranding = (config: IInstanceConfig | undefined): void => {
  if (!config || typeof window === "undefined") return;
  try {
    const branding: TFailurePageBranding = {
      supportText: config.support_text ?? "",
      showExternalLinks: config.show_external_links === true,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(branding));
  } catch {
    // A quota or a private window. The failure pages fall back to saying less,
    // which is the safe direction.
  }
};

export const recalledFailurePageBranding = (): TFailurePageBranding => {
  if (typeof window === "undefined") return EMPTY;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return EMPTY;
    const parsed = JSON.parse(stored) as Partial<TFailurePageBranding>;
    return {
      supportText: typeof parsed.supportText === "string" ? parsed.supportText : "",
      showExternalLinks: parsed.showExternalLinks === true,
    };
  } catch {
    return EMPTY;
  }
};
