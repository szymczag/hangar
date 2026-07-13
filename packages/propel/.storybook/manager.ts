/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { addons } from "storybook/manager-api";
import { create } from "storybook/theming";

const hangarTheme = create({
  base: "dark",
  brandTitle: "Hangar UI",
  brandUrl: "https://github.com/szymczag/hangar",
  brandTarget: "_self",
});

addons.setConfig({
  theme: hangarTheme,
});
