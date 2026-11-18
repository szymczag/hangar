/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// The editor source imports through the tsconfig alias (`@/...`); tests that
// load extensions need it resolved.
const resolve = { tsconfigPaths: true };

export default {
  resolve,
  test: {
    projects: [
      {
        resolve,
        test: {
          name: "node",
          environment: "node",
          // The security suites run without a DOM so they exercise the Node
          // entry of @tiptap/html; src/** holds unit tests that sit beside their
          // module (markdown-paste).
          include: ["tests/**/*.test.ts", "src/**/*.test.ts"],
          exclude: ["src/**/__tests__/**"],
        },
      },
      {
        resolve,
        test: {
          name: "dom",
          // Upstream's editor and hook tests render into a document.
          environment: "happy-dom",
          include: ["src/**/__tests__/**/*.test.ts"],
        },
      },
    ],
  },
};
