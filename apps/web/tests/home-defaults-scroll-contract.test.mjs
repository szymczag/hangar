// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(
  new URL("../app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/home-defaults/page.tsx", import.meta.url),
  "utf8"
);

test("home defaults owns a settings scroll container in every render state", () => {
  assert.match(page, /import \{ SettingsContentWrapper \} from "@\/components\/settings\/content-wrapper";/);

  const wrappers = page.match(/<SettingsContentWrapper>/g) ?? [];
  assert.equal(wrappers.length, 2, "the loading and loaded states must both use the settings scroll container");
});
