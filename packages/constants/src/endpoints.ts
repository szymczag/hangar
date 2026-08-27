/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

type HangarRuntimeConfig = {
  VITE_ADMIN_BASE_URL?: string;
  VITE_SPACE_BASE_URL?: string;
  VITE_LIVE_BASE_URL?: string;
  VITE_LIVE_BASE_PATH?: string;
  VITE_WEB_BASE_URL?: string;
  VITE_API_BASE_URL?: string;
};

const runtimeConfig =
  typeof globalThis === "undefined"
    ? undefined
    : (globalThis as typeof globalThis & { __HANGAR_CONFIG__?: HangarRuntimeConfig }).__HANGAR_CONFIG__;

export const API_BASE_URL = runtimeConfig?.VITE_API_BASE_URL || process.env.VITE_API_BASE_URL || "";
export const API_BASE_PATH = process.env.VITE_API_BASE_PATH || "";
export const API_URL = encodeURI(`${API_BASE_URL}${API_BASE_PATH}`);
// God Mode Admin App Base Url
export const ADMIN_BASE_URL = runtimeConfig?.VITE_ADMIN_BASE_URL || process.env.VITE_ADMIN_BASE_URL || "";
export const ADMIN_BASE_PATH = process.env.VITE_ADMIN_BASE_PATH || "";
export const GOD_MODE_URL = encodeURI(`${ADMIN_BASE_URL}${ADMIN_BASE_PATH}`);
// Publish App Base Url
export const SPACE_BASE_URL = runtimeConfig?.VITE_SPACE_BASE_URL || process.env.VITE_SPACE_BASE_URL || "";
export const SPACE_BASE_PATH = process.env.VITE_SPACE_BASE_PATH || "";
export const SITES_URL = encodeURI(`${SPACE_BASE_URL}${SPACE_BASE_PATH}`);
// Live App Base Url
export const LIVE_BASE_URL = runtimeConfig?.VITE_LIVE_BASE_URL || process.env.VITE_LIVE_BASE_URL || "";
export const LIVE_BASE_PATH = runtimeConfig?.VITE_LIVE_BASE_PATH || process.env.VITE_LIVE_BASE_PATH || "/live";
export const LIVE_URL = encodeURI(`${LIVE_BASE_URL}${LIVE_BASE_PATH}`);
// Web App Base Url
export const WEB_BASE_URL = runtimeConfig?.VITE_WEB_BASE_URL || process.env.VITE_WEB_BASE_URL || "";
export const WEB_BASE_PATH = process.env.VITE_WEB_BASE_PATH || "";
export const WEB_URL = encodeURI(`${WEB_BASE_URL}${WEB_BASE_PATH}`);
// Hangar project destinations. Runtime instance metadata can override these
// links for independently operated installations.
export const WEBSITE_URL = process.env.VITE_WEBSITE_URL || "https://github.com/szymczag/hangar";
export const DOCUMENTATION_URL = process.env.VITE_DOCUMENTATION_URL || `${WEBSITE_URL}#readme`;
export const ISSUE_TRACKER_URL = process.env.VITE_ISSUE_TRACKER_URL || `${WEBSITE_URL}/issues`;
export const SECURITY_REPORT_URL = process.env.VITE_SECURITY_REPORT_URL || `${WEBSITE_URL}/security/advisories/new`;
export const SOURCE_CODE_URL = process.env.VITE_SOURCE_CODE_URL || WEBSITE_URL;
export const TERMS_URL = process.env.VITE_TERMS_URL || "";
export const PRIVACY_URL = process.env.VITE_PRIVACY_URL || "";

// Compatibility exports retained for upstream call sites. They intentionally
// resolve to Hangar resources and never to Hangar commercial services.
export const SUPPORT_EMAIL = "";
export const MARKETING_PRICING_PAGE_LINK = DOCUMENTATION_URL;
export const MARKETING_CONTACT_US_PAGE_LINK = ISSUE_TRACKER_URL;
export const MARKETING_PLANE_ONE_PAGE_LINK = DOCUMENTATION_URL;
