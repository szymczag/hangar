/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export declare const TRUSTED_TYPES_POLICY_NAMES: readonly string[];

export declare const OBSERVE_MAX_LENGTH: number;

export declare const EDITOR_SANITIZE_CONFIG: Readonly<{
  ADD_TAGS: string[];
  ADD_ATTR: string[];
  FORBID_ATTR: string[];
}>;

/** The string as TrustedHTML from the "hangar-inert" policy, for DOMParser only; the string itself without Trusted Types. */
export declare const inertHTML: (html: string) => string;

export declare const installTrustedTypesPolicies: (options?: {
  reportUrl?: string;
  sanitize?: (value: string) => string;
  send?: (url: string, body: string) => unknown;
}) => boolean;
