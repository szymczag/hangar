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
import { setEmojiDataUrl } from "@plane/blocks/emoji-icon-picker";

// Trusted Types policies (docs/trusted-types-plan.md), before React renders
// anything: library code that hands HTML strings to the DOM goes through the
// default policy from its first render. They only observe and report; no
// value is changed.
installTrustedTypesPolicies({ reportUrl: `${API_BASE_URL}/api/csp-report/` });

// The emoji picker reads its data from this app, under whatever base path it
// is served on (packages/csp/src/vite-emoji-data.mjs), never from a CDN.
setEmojiDataUrl(`${import.meta.env.BASE_URL}emojibase`);

// Initialize i18n before hydrating (the remix-i18next pattern for React
// Router: await init, then hydrateRoot). The server renders with an
// initialized instance; hydrating before the client instance is ready would
// make the first client render diverge from the server HTML, and React 19
// leaves server DOM it could not adopt in place instead of clearing it.
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
