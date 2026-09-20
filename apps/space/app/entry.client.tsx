/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { startTransition, StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { API_BASE_URL } from "@plane/constants";
import { installTrustedTypesPolicies } from "@plane/csp/trusted-types";
import { setEmojiDataUrl } from "@plane/propel/emoji-icon-picker";

// Trusted Types policies (docs/trusted-types-plan.md), before React renders
// anything: library code that hands HTML strings to the DOM goes through the
// default policy from its first render. They only observe and report; no
// value is changed.
installTrustedTypesPolicies({ reportUrl: `${API_BASE_URL}/api/csp-report/` });

// The emoji picker reads its data from this app, under whatever base path it
// is served on (scripts/vite-emoji-data.mjs), never from a CDN.
setEmojiDataUrl(`${import.meta.env.BASE_URL}emojibase`);

startTransition(() => {
  hydrateRoot(
    document,
    <StrictMode>
      <HydratedRouter />
    </StrictMode>
  );
});
