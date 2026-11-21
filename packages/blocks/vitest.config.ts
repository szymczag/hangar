/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.stories.{ts,tsx}", "src/**/index.ts", "src/**/*types*.{ts,tsx}"],
    },
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          include: ["src/**/*.test.ts"],
          environment: "node",
        },
      },
      {
        // Component tests that need a DOM but not a real browser, so `pnpm test` stays runnable
        // without browsers.
        extends: true,
        test: {
          name: "dom",
          include: ["src/**/*.test.tsx"],
          // Hangar: this file tests upstream v1.5.0's useOutsideClickDetector (Base UI portal
          // awareness, `enabled` flag). Hangar's @plane/hooks keeps the 1.4 hook, which 43 web
          // files share, so adopting it is a behaviour change for later. See FORK.md.
          exclude: ["src/property-select/outside-click.test.tsx"],
          environment: "jsdom",
          setupFiles: ["./vitest.setup.dom.ts"],
        },
      },
    ],
  },
});
