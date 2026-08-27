/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export default {
  test: {
    environment: "node",
    // Restricted to TypeScript suites. apps/web/tests/*.test.mjs are node:test
    // contracts with no vitest suite in them, run separately by the
    // test:react-runtime-contracts script; without this vitest collects them
    // and fails on files that are not its own.
    include: ["**/*.test.ts", "**/*.test.tsx"],
    exclude: ["**/node_modules/**", "**/build/**", "**/dist/**"],
  },
};
