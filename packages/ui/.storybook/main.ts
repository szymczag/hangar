/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { StorybookConfig } from "@storybook/react-vite";

import { createRequire } from "module";
import { join, dirname } from "path";

const require = createRequire(import.meta.url);

/**
 * This function is used to resolve the absolute path of a package.
 * It is needed in projects that use Plug'n'Play (PnP) or are set up within a monorepo.
 */
function getAbsolutePath(value: string): any {
  return dirname(require.resolve(join(value, "package.json")));
}
const config: StorybookConfig = {
  stories: ["../src/**/*.mdx", "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)"],
  addons: [getAbsolutePath("@storybook/addon-links"), getAbsolutePath("@storybook/addon-docs")],
  framework: {
    // Vite, matching packages/propel. The webpack builder this used to name has
    // no postcss step: its default CSS rule is style-loader + css-loader only,
    // and the `@storybook/addon-styling-webpack` that was meant to supply one
    // was registered as a bare string with no options, which makes it a no-op.
    // Tailwind therefore never ran, which is why this Storybook depended on a
    // pre-built stylesheet that nothing built. Vite picks up postcss.config.js
    // on its own, so the source CSS is processed with no wiring at all.
    name: getAbsolutePath("@storybook/react-vite"),
    options: {},
  },
};
export default config;
