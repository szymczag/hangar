/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Preview } from "@storybook/react-vite";
// The source stylesheet, which is `@import "@plane/tailwind-config/index.css"`
// and nothing else. This used to import ../styles/output.css -- a build
// artifact that is gitignored and produced only by a `postcss --watch` script
// nothing invoked, so this Storybook could not start on a clean checkout.
// A stylesheet import has no binding to assign, which is the whole point of it.
// packages/propel/.storybook/preview.ts carries the same warning; it simply has
// not been staged since the rule was turned on, so the hook has never seen it.
// oxlint-disable-next-line eslint-plugin-import/no-unassigned-import
import "../styles/globals.css";
const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
  },
};

export default preview;
