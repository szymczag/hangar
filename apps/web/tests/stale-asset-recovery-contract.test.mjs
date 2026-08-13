// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const helperSource = readFileSync(new URL("../core/lib/stale-asset-error.ts", import.meta.url), "utf8");
const entrySource = readFileSync(new URL("../app/entry.client.tsx", import.meta.url), "utf8");
const rootSource = readFileSync(new URL("../app/root.tsx", import.meta.url), "utf8");

test("recognizes stale JavaScript and CSS asset failures", () => {
  for (const signature of [
    "Failed to fetch dynamically imported module",
    "error loading dynamically imported module",
    "Importing a module script failed",
    "Unable to preload CSS",
    "No result returned from dataStrategy for route",
  ]) {
    assert.ok(helperSource.includes(signature), `missing stale-asset signature: ${signature}`);
  }
});

test("limits stale-asset recovery to one production reload window", () => {
  assert.match(helperSource, /__hangar_chunk_reload/);
  assert.match(helperSource, /STALE_ASSET_RELOAD_WINDOW_MS = 30_000/);
  assert.match(helperSource, /sessionStorage\.setItem/);
  assert.match(helperSource, /window\.location\.reload\(\)/);
  assert.match(entrySource, /if \(import\.meta\.env\.PROD\)/);
  assert.match(entrySource, /vite:preloadError/);
  assert.match(rootSource, /isStaleAssetError\(error\)/);
});
