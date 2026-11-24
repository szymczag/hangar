// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The Hangar wordmark is white artwork drawn for a dark surface. On the
 * sign-in, sign-up, password and onboarding headers, which sit on the theme's
 * own surface, it was nearly invisible in light themes. Those headers ask for
 * the themed wordmark, which inverts the artwork outside dark themes.
 *
 * The same holds for every other wordmark on a theme surface: the invitations
 * and create-workspace pages, the "not a member" workspace list, the instance
 * not-ready view, the product updates footer button, and the space app's
 * failure page (over the theme's own pattern) and signed-in page. The tour's
 * welcome card keeps the white artwork: it sits on the fixed accent fill.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (relative) => readFileSync(new URL(`../../../${relative}`, import.meta.url), "utf8");

const SURFACES = [
  "apps/web/components/auth-screens/header.tsx",
  "apps/web/components/onboarding/header.tsx",
  "apps/admin/app/(all)/(home)/auth-header.tsx",
  "apps/space/components/views/header.tsx",
  "apps/web/app/(all)/invitations/page.tsx",
  "apps/web/app/(all)/create-workspace/page.tsx",
  "apps/web/layouts/auth-layout/workspace-wrapper.tsx",
  "apps/web/components/instance/not-ready-view.tsx",
  "apps/web/components/global/product-updates/footer.tsx",
  "apps/space/lib/instance-provider.tsx",
  "apps/space/components/account/user-logged-in.tsx",
];

for (const surface of SURFACES) {
  test(`${surface} renders the themed wordmark`, () => {
    const source = read(surface);
    assert.match(source, /<HangarLogo themed\b/, "the wordmark sits on the theme surface and needs the themed variant");
    assert.doesNotMatch(source, /<HangarLogo(?![^>]*\bthemed\b)[^>]*\/>/, "no untreated wordmark left on this surface");
  });
}

test("the tour's welcome card keeps the artwork as drawn on its accent fill", () => {
  const source = read("apps/web/components/onboarding/tour/root.tsx");
  assert.match(source, /bg-accent-primary">\s*<HangarLogo className="h-10 w-auto" \/>/);
});

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
