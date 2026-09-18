/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export default {
  resolve: {
    // The editor source imports through the tsconfig aliases (`@/...`,
    // `@/plane-editor/...`); tests that load extensions need them resolved.
    tsconfigPaths: true,
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
};
