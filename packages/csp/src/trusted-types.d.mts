/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TTrustedTypesMode = "off" | "report" | "enforce";

export declare const TRUSTED_TYPES_POLICY_NAMES: readonly string[];

export declare const TRUSTED_TYPES_MODES: readonly TTrustedTypesMode[];

export declare const DEFAULT_TRUSTED_TYPES_MODE: "report";

export declare const TRUSTED_TYPES_META_NAME: "hangar-trusted-types";

/** HANGAR_CSP_TRUSTED_TYPES, defaulting to "report"; for server rendering. */
export declare const trustedTypesModeFromEnv: (env?: Record<string, string | undefined>) => TTrustedTypesMode;

/** The mode the document's <head> meta names, defaulting to "report". */
export declare const trustedTypesModeFromDocument: (doc?: Document) => TTrustedTypesMode;

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
  mode?: TTrustedTypesMode;
  sanitize?: (value: string) => string;
  send?: (url: string, body: string) => unknown;
}) => boolean;

export declare const KNOWN_LIBRARY_SCRIPTS: ReadonlyArray<{
  readonly name: string;
  readonly matches: (value: string) => boolean;
}>;
