// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The Hangar wordmark is white artwork drawn for a dark surface. On the
 * sign-in, sign-up, password and onboarding headers, which sit on the theme's
 * own surface, it was nearly invisible in light themes. Those headers ask for
 * the themed wordmark, which inverts the artwork outside dark themes.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (relative) => readFileSync(new URL(`../../../${relative}`, import.meta.url), "utf8");

const HEADERS = [
  "apps/web/components/auth-screens/header.tsx",
  "apps/web/components/onboarding/header.tsx",
  "apps/admin/app/(all)/(home)/auth-header.tsx",
  "apps/space/components/views/header.tsx",
];

for (const header of HEADERS) {
  test(`${header} renders the themed wordmark`, () => {
    const source = read(header);
    assert.match(source, /<HangarLogo themed\b/, "the header sits on the theme surface and needs the themed wordmark");
    assert.doesNotMatch(source, /<HangarLogo(?![^>]*\bthemed\b)[^>]*\/>/, "no untreated wordmark left in the header");
  });
}

test("the themed wordmark inverts in light themes and is left as drawn in dark ones", () => {
  const blocks = read("packages/blocks/src/icons/brand/hangar-logo.tsx");
  assert.match(
    blocks,
    /HANGAR_LOGO_THEMED_CLASSNAME = "invert hue-rotate-180 dark:invert-0 dark:hue-rotate-0"/,
    "invert turns the white letters dark, hue-rotate keeps the chevrons blue, dark: restores the artwork"
  );
  assert.match(blocks, /themed \? HANGAR_LOGO_THEMED_CLASSNAME/);
});

test("the propel copy of the logo stays identical to the blocks one", () => {
  assert.equal(
    read("packages/propel/src/icons/brand/hangar-logo.tsx"),
    read("packages/blocks/src/icons/brand/hangar-logo.tsx")
  );
});
