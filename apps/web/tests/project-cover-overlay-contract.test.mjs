// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The project settings header writes the project's name in white over its
 * cover, readable only through the dark gradient laid over the cover.
 *
 * A project without a cover shows a pulsing placeholder instead of an image.
 * The pulse animates opacity, which gives the placeholder its own stacking
 * context and paints it above any overlay that comes earlier in the markup, so
 * in a light theme the name sat white on a near-white surface. The overlay has
 * to follow the cover to stay on top of both.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../components/project/form.tsx", import.meta.url), "utf8");

test("the gradient overlay is painted over the cover, not under it", () => {
  const cover = source.indexOf("<CoverImage src={coverImage}");
  const overlay = source.indexOf("bg-gradient-to-t from-black/80");
  assert.ok(cover !== -1, "the header must still render the cover");
  assert.ok(overlay !== -1, "the header must still darken the cover behind the name");
  assert.ok(overlay > cover, "the overlay must come after CoverImage so it stays above the placeholder");
});

test("the overlay does not swallow clicks meant for the header", () => {
  assert.match(source, /pointer-events-none absolute inset-0 rounded-md bg-gradient-to-t/);
});

test("the name over the cover still uses the on-colour text token", () => {
  assert.match(source, /flex flex-col gap-1 truncate text-on-color/);
});
