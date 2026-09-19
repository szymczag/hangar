/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export declare const RUNTIME_STYLE_ELEMENTS: readonly string[];

export declare const APP_SOURCES: { readonly connectSrc: readonly string[]; readonly imgSrc: readonly string[] };

export declare const DEFAULT_REPORT_ONLY: boolean;
export declare const DEFAULT_REPORT_URI: string;

export declare const hashSource: (content: string) => string;

export declare const inlineScriptHashes: (html: string) => string[];

export type TContentSecurityPolicyOptions = {
  scriptSources?: string[];
  styleElementSources?: string[];
  imgSrc?: string;
  connectSrc?: string;
  mediaSrc?: string;
  frameSrc?: string;
  formAction?: string;
  frameAncestors?: string;
  reportUri?: string;
};

export declare const buildContentSecurityPolicy: (options?: TContentSecurityPolicyOptions) => string;

export declare const runtimeSourcesFromEnv: (
  env?: Record<string, string | undefined>
) => Required<
  Pick<TContentSecurityPolicyOptions, "imgSrc" | "connectSrc" | "mediaSrc" | "frameSrc" | "formAction" | "reportUri">
>;

export declare const policyHeaderName: (
  env?: Record<string, string | undefined>
) => "Content-Security-Policy" | "Content-Security-Policy-Report-Only";

export declare const TRUSTED_TYPES_MEASUREMENT: string;

export declare const trustedTypesModeFromEnv: (env?: Record<string, string | undefined>) => "report" | "off";

export declare const trustedTypesReportPolicy: (options?: { reportUri?: string; mode?: "report" | "off" }) => string;
