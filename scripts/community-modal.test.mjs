// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const content = JSON.parse(
  readFileSync(new URL("../apps/web/ce/components/license/modal/community-modal-content.json", import.meta.url), "utf8")
);
const generated = readFileSync(
  new URL("../apps/web/ce/components/license/release-notes.generated.ts", import.meta.url),
  "utf8"
);

test("describes Hangar capabilities without advertising upstream plans", () => {
  const copy = JSON.stringify(content);

  // The dialog used to carry this guarantee in a headline above a check-marked
  // feature grid. The grid is gone -- it read like a pricing page and, being a
  // hand-maintained list, could not track what the build actually contained.
  // The guarantee itself moved into the description and still has to be there.
  assert.match(content.description, /no paid tier/i);
  assert.match(content.description, /Every capability in this build is included/);
  assert.doesNotMatch(copy, /upgrade to|unlock|Plane (?:Pro|Business|Enterprise)/i);
});

test("keeps the upstream relationship explicit", () => {
  assert.match(content.attribution, /independent, community-maintained fork/);
  assert.match(content.attribution, /not affiliated with, endorsed by, or supported by/);
  assert.match(content.attribution, /commercial products are separate offerings/);
});

test("the bundled release notes do not become a sales pitch", () => {
  // The highlights are generated from docs/releases, which is prose somebody
  // writes by hand. The same rule that governs the dialog's own copy applies.
  assert.doesNotMatch(generated, /upgrade to|unlock|Plane (?:Pro|Business|Enterprise)/i);
});

test("the release notes are bundled rather than fetched", () => {
  const modal = readFileSync(
    new URL("../apps/web/ce/components/license/modal/community-modal.tsx", import.meta.url),
    "utf8"
  );

  assert.match(modal, /from "\.\.\/release-notes\.generated"/, "notes must come from the generated module");
  // Guards the reason the notes were bundled in the first place: opening this
  // dialog must not reach off-instance for anything.
  assert.doesNotMatch(modal, /fetch\(|useSWR|axios/, "the dialog must not request anything when it opens");
});

test("notes from a different build are not shown as though they were this one", () => {
  const modal = readFileSync(
    new URL("../apps/web/ce/components/license/modal/community-modal.tsx", import.meta.url),
    "utf8"
  );

  assert.match(
    modal,
    /RELEASE_NOTES\.version === version \? RELEASE_NOTES\.highlights : \[\]/,
    "highlights must be gated on the bundled version matching the running one"
  );
});
