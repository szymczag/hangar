// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const WEB = path.dirname(path.dirname(fileURLToPath(new URL("../tests/x", import.meta.url))));
const source = (relativePath) => readFileSync(path.join(WEB, relativePath), "utf8");

test("the compact work-item route is registered inside the authenticated workspace layouts", () => {
  const routes = source("app/routes/extended.ts");
  assert.match(routes, /route\("i\/:workItem", "\.\/\(all\)\/short-work-item\/page\.tsx"\)/);
  assert.match(routes, /browse\/\[workItem\]\/layout\.tsx/);
});

test("route compatibility supplies the configured slug and rewrites only browse links", () => {
  const policy = source("app/compat/next/route-policy-context.tsx");
  assert.match(policy, /params\.workItem && !params\.workspaceSlug && defaultWorkspaceSlug/);
  assert.match(policy, /browse\/\(\[\^\/\]\+\)/);
  assert.doesNotMatch(policy, /projects\/|workspace-views\/|archives\//);
});

test("links and imperative navigation share the same route policy", () => {
  assert.match(source("app/compat/next/link.tsx"), /normalizePath\(href\)/);
  const navigation = source("app/compat/next/navigation.ts");
  assert.match(navigation, /normalizePath\(to\)/);
  assert.match(source("core/lib/wrappers/store-wrapper.tsx"), /normalizeDefaultWorkspacePath/);
});
