/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export default {
  resolve: {
    // The editor source imports through the tsconfig alias (`@/...`); tests
    // that load extensions need it resolved.
    tsconfigPaths: true,
  },
  test: {
    environment: "node",
    // src/** holds unit tests that sit beside their module (markdown-paste).
    include: ["tests/**/*.test.ts", "src/**/*.test.ts"],
  },
};
