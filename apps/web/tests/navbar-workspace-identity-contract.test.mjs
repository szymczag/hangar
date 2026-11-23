// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const WEB = path.dirname(path.dirname(fileURLToPath(new URL("../tests/x", import.meta.url))));

const source = (relativePath) => readFileSync(path.join(WEB, relativePath), "utf8");

test("the top navigation gives the workspace identity room without crowding narrow screens", () => {
  const navigation = source("components/navigation/top-navigation-root.tsx");
  const workspaceMenu = source("components/workspace/sidebar/workspace-menu-root.tsx");
  const commandSearch = source("components/navigation/top-nav-power-k.tsx");

  assert.match(navigation, /h-12 min-h-12/);
  assert.match(workspaceMenu, /sm:max-w-48 md:max-w-60 xl:max-w-72/);
  // Propel's largest workspace avatar (32px) in the top navigation, as the
  // 36px logo was before the move to Propel.
  assert.match(workspaceMenu, /<WorkspaceAvatar\s+size="lg"/);
  assert.match(workspaceMenu, /hidden min-w-0 truncate text-body-sm-medium text-primary sm:block/);
  assert.match(workspaceMenu, /<Tooltip label=\{activeWorkspace\?\.name/);
  assert.match(commandSearch, /w-\[clamp\(12rem,32vw,22\.75rem\)\]/);
});
