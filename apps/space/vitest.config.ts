/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Separate from vite.config.ts, which loads the React Router plugin; the unit
// suites need only the `@/` alias. Restricted to TypeScript suites: the
// tests/*.build.test.mjs files are node:test checks of the built app, run by
// test:space-build after a build.
export default {
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/build/**", "**/dist/**"],
  },
};
