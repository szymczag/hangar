// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Onboarding must not render a step before it knows which one applies.
 *
 * The component used to start at PROFILE_SETUP, so that screen rendered on
 * mount — before the workspace list had loaded and before anything had decided
 * whether there was a question to ask. Someone with a membership and a
 * provider-supplied name saw a name field and an avatar picker flash past on
 * the way out, offering exactly what had just been made read-only elsewhere.
 *
 * The server keeps most people away from here entirely by settling the flags
 * that routing reads. This is the second line: whatever the reason for arriving,
 * nothing is shown until the step is chosen.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../core/components/onboarding/root.tsx", import.meta.url), "utf8");

test("no step is assumed before one is chosen", () => {
  assert.doesNotMatch(
    source,
    /useState<TOnboardingStep>\(EOnboardingSteps\.PROFILE_SETUP\)/,
    "starting at a step renders it on mount, which is the flash"
  );
  assert.match(source, /useState<TOnboardingStep \| undefined>\(undefined\)/);
});

test("nothing renders until then", () => {
  assert.match(
    source,
    /if \(!currentStep\) return null;/,
    "without this the step components are asked to render an undefined step"
  );
});

test("the decision waits for the data it depends on", () => {
  assert.match(
    source,
    /if \(workspacesLoader \|\| !userProfile\) return;/,
    "deciding on a half-loaded picture is what produced the flash"
  );
  assert.match(source, /workspacesLoader,/, "the effect has to re-run when loading finishes");
});
