// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const content = JSON.parse(
  readFileSync(new URL("../apps/web/ce/components/license/modal/community-modal-content.json", import.meta.url), "utf8")
);

test("describes Hangar capabilities without advertising upstream plans", () => {
  const copy = JSON.stringify(content);

  assert.match(content.title, /No paid Hangar plan required/);
  assert.doesNotMatch(copy, /upgrade to|unlock|Plane (?:Pro|Business|Enterprise)/i);
  assert.deepEqual(content.features, [
    "OIDC and SAML single sign-on",
    "Epics",
    "Custom work-item types and properties",
    "Time tracking and worklogs",
  ]);
});

test("keeps the upstream relationship explicit", () => {
  assert.match(content.attribution, /independent, community-maintained fork/);
  assert.match(content.attribution, /not affiliated with, endorsed by, or supported by/);
  assert.match(content.attribution, /commercial products are separate offerings/);
});
