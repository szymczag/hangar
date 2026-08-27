// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const source = (relativePath) => readFileSync(path.join(ROOT, relativePath), "utf8");

test("Live collaboration has a runtime path and a safe image fallback", () => {
  const endpoints = source("packages/constants/src/endpoints.ts");
  assert.match(endpoints, /runtimeConfig\?\.VITE_LIVE_BASE_PATH/);
  assert.match(endpoints, /process\.env\.VITE_LIVE_BASE_PATH \|\| "\/live"/);

  const runtimeConfig = source("charts/hangar/templates/frontend-configmap.yaml");
  assert.match(runtimeConfig, /VITE_LIVE_BASE_PATH: "\/live"/);

  const releaseWorkflow = source(".github/workflows/build-branch.yml");
  assert.match(releaseWorkflow, /VITE_LIVE_BASE_PATH=\/live/);
});

test("the editor appends collaboration below the configured Live path", () => {
  const editor = source("apps/web/core/components/pages/editor/editor-body.tsx");
  assert.match(editor, /WS_LIVE_URL\.pathname = `\$\{LIVE_BASE_PATH\}\/collaboration`/);
});
