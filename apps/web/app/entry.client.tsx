/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { initPromise } from "@plane/i18n";
import { startTransition, StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { API_BASE_URL } from "@plane/constants";
import { installTrustedTypesPolicies } from "@plane/csp/trusted-types";
import { setEmojiDataUrl as setBlocksEmojiDataUrl } from "@plane/blocks/emoji-icon-picker";
import { setEmojiDataUrl } from "@plane/propel/emoji-icon-picker";

import polyfills from "@/lib/polyfills";
import { isStaleAssetErrorMessage, recoverFromStaleAsset } from "@/lib/stale-asset-error";

void polyfills;

// Production-only: in dev these errors come from the dev server itself (restarts,
// stale optimized deps) and auto-reloading would mask them.
if (import.meta.env.PROD) {
  window.addEventListener("vite:preloadError", (event) => {
    if (recoverFromStaleAsset()) event.preventDefault();
  });

  window.addEventListener("error", (event) => {
    if (isStaleAssetErrorMessage(event.message || "")) recoverFromStaleAsset();
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason ?? "");
    if (isStaleAssetErrorMessage(reason)) recoverFromStaleAsset();
  });
}

// Trusted Types policies (docs/trusted-types-plan.md), before React renders
// anything: library code that hands HTML strings to the DOM goes through the
// default policy from its first render. They only observe and report; no
// value is changed.
installTrustedTypesPolicies({ reportUrl: `${API_BASE_URL}/api/csp-report/` });

// The emoji pickers read their data from this app, under whatever base path it
// is served on (packages/csp/src/vite-emoji-data.mjs), never from a CDN. Web
// itself only renders the blocks picker; the 1.4 one (@plane/propel) is still
// pointed at it because the editor's callout logo picker renders it.
const emojiDataUrl = `${import.meta.env.BASE_URL}emojibase`;
setEmojiDataUrl(emojiDataUrl);
setBlocksEmojiDataUrl(emojiDataUrl);

// Initialize i18n before hydrating (the remix-i18next pattern for React
// Router: await init, then hydrateRoot), as upstream makeplane/plane 1a76f29c79
// does. Hydrating before the instance is ready would make the first client
// render diverge from the prerendered shell, and React 19 leaves DOM it could
// not adopt in place instead of clearing it. The policies and emoji data URL
// above are set first, so nothing renders without them.
const hydrate = () =>
  startTransition(() => {
    hydrateRoot(
      document,
      <StrictMode>
        <HydratedRouter />
      </StrictMode>
    );
  });

void initPromise.catch(() => {}).then(hydrate);
