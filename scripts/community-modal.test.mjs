// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const content = JSON.parse(
  readFileSync(new URL("../apps/web/ce/components/license/modal/community-modal-content.json", import.meta.url), "utf8")
);
/** Strip the tag's leading `v`, which only the running version carries. */
const strip = (value) => value.replace(/^v/, "");

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
    /sameVersion\(RELEASE_NOTES\.version, version\) \? RELEASE_NOTES\.highlights : \[\]/,
    "highlights must be gated on the bundled version matching the running one"
  );
});

test("the gate actually matches the version the API reports", () => {
  // The two sides spell the version differently and always have: the release
  // file is `hangar-v<version>.md`, so the generator yields "0.1.0-rc.41",
  // while APP_VERSION carries the tag's leading `v`. Compared raw, the gate was
  // permanently false and the highlights were silently off in EVERY build --
  // which is exactly what shipped in rc.41. The previous test passed anyway,
  // because it only ever checked each side in isolation.
  const bundled = /"?version"?:\s*"([^"]+)"/.exec(generated)?.[1];
  assert.ok(bundled, "the generated module must carry a version");

  assert.equal(
    strip(bundled),
    strip(`v${bundled}`),
    "the comparison must ignore the leading v that only the running version carries"
  );

  // And the component must not go back to comparing them raw.
  const modal = readFileSync(
    new URL("../apps/web/ce/components/license/modal/community-modal.tsx", import.meta.url),
    "utf8"
  );
  assert.doesNotMatch(
    modal,
    /RELEASE_NOTES\.version === version/,
    "a raw === between the bundled and running versions can never be true"
  );
  assert.match(modal, /replace\(\/\^v\/, ""\)/, "the leading v must be stripped before comparing");
});

test("a highlight that wraps across lines is still picked up", async () => {
  // The lead-ins are hand-written prose, so the long ones wrap. Matching only
  // single-line ones dropped exactly those -- and the longest tend to be the
  // most important -- with nothing to show that anything was missing.
  const { latestReleaseNotes } = await import("./generate-release-notes.mjs");
  const { mkdtempSync, writeFileSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const { join } = await import("node:path");

  const dir = mkdtempSync(join(tmpdir(), "release-notes-"));
  writeFileSync(
    join(dir, "hangar-v9.9.9.md"),
    [
      "## Security and privacy",
      "",
      "**One line.** Body.",
      "",
      "**A lead-in long enough that it wraps onto",
      "a second line before it closes.** Body.",
      "",
    ].join("\n")
  );

  const { highlights } = latestReleaseNotes(dir);
  assert.deepEqual(highlights, [
    "One line.",
    "A lead-in long enough that it wraps onto a second line before it closes.",
  ]);
});
