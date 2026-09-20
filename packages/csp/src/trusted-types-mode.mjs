/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// How Trusted Types is applied (HANGAR_CSP_TRUSTED_TYPES), shared by the
// header generators and the browser policies. No dependencies: both Node and
// the client bundles import it.
//
// - "report" (default): the Trusted Types policy is report-only and the
//   default policy only observes (docs/trusted-types-plan.md, phase 2).
// - "enforce": the policy is enforced and the default policy sanitizes
//   (phase 4, opt-in until a release cycle has produced no reports).
// - "off": no Trusted Types header; the policies still install, harmlessly.

export const TRUSTED_TYPES_MODES = Object.freeze(["off", "report", "enforce"]);

export const DEFAULT_TRUSTED_TYPES_MODE = "report";

/** An unknown value falls back to the default rather than to enforcing. */
export const trustedTypesModeFromEnv = (env = globalThis.process?.env ?? {}) => {
  const value = env.HANGAR_CSP_TRUSTED_TYPES;
  return TRUSTED_TYPES_MODES.includes(value) ? value : DEFAULT_TRUSTED_TYPES_MODE;
};

/**
 * The document tells the client which mode its headers are in, through
 * `<meta name="hangar-trusted-types" content="…">` in <head>: rendered per
 * request by space, rewritten by nginx for the single-page apps. The value
 * written into the built HTML is the default, which nginx replaces.
 */
export const TRUSTED_TYPES_META_NAME = "hangar-trusted-types";

export const trustedTypesMetaTag = (mode = DEFAULT_TRUSTED_TYPES_MODE) =>
  `<meta name="${TRUSTED_TYPES_META_NAME}" content="${mode}"`;
