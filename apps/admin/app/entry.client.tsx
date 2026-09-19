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

// Trusted Types policies (docs/trusted-types-plan.md), before React renders
// anything: library code that hands HTML strings to the DOM goes through the
// default policy from its first render. They only observe and report; no
// value is changed.
installTrustedTypesPolicies({ reportUrl: `${API_BASE_URL}/api/csp-report/` });

startTransition(() => {
  hydrateRoot(
    document,
    <StrictMode>
      <HydratedRouter />
    </StrictMode>
  );
});
