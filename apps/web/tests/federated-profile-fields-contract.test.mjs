// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The application must not offer to edit what the provider owns.
 *
 * Two different rules, deliberately kept apart:
 *
 *   - Name, display name and avatar are rewritten by attribute sync on every
 *     sign-in, so they are read-only only where sync is on for the provider the
 *     account uses. An account federated with sync off owns them.
 *   - The email address is refused by the API for any federated account, sync or
 *     not, because domain policy reads it.
 *
 * Onboarding and profile settings ask the first question of the same two values
 * and must not drift, which is what the shared helper is for.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

const helper = read("../helpers/provider-managed-profile.ts");
const settings = read("../core/components/settings/profile/content/pages/general/form.tsx");
const onboarding = read("../core/components/onboarding/steps/profile/root.tsx");

test("both places decide it with the same helper", () => {
  for (const [name, source] of [
    ["profile settings", settings],
    ["onboarding", onboarding],
  ]) {
    assert.match(source, /isProfileManagedByProvider\(/, `${name} should ask the shared helper`);
    assert.doesNotMatch(
      source,
      /provider_managed_profiles \?\? \[\]\)\.includes/,
      `${name} re-derives the rule instead of sharing it, so the two can drift apart`
    );
  }
});

test("the helper reads sync, not federation", () => {
  assert.match(helper, /provider_managed_profiles/);
  assert.match(helper, /last_login_medium/);
  assert.doesNotMatch(
    helper,
    /is_federated/,
    "an account can be federated with sync off, and then these fields are its own"
  );
});

test("the fields the provider rewrites are not editable", () => {
  for (const field of ["first name", "last name", "display name"]) {
    const placeholder = `placeholder="Enter your ${field}"`;
    const at = settings.indexOf(placeholder);
    assert.ok(at !== -1, `expected the ${field} input; this test is looking at the wrong shape`);
    assert.match(
      settings.slice(at, at + 200),
      /disabled=\{providerManagesProfile\}/,
      `${field} stays editable, so an edit survives until the next sign-in and no further`
    );
  }
});

test("the avatar upload is not offered, because sync deletes the file", () => {
  assert.match(settings, /disabled=\{providerManagesProfile\}/);
  assert.match(
    settings,
    /!providerManagesProfile && setIsImageUploadModalOpen\(true\)/,
    "the picture itself opens the same modal and has to be guarded too"
  );
});

test("a federated account is not offered an address it cannot change", () => {
  assert.match(
    settings,
    /isFederated \? \(/,
    "the change-email offer must depend on federation, which the API refuses on"
  );
  assert.match(settings, /Boolean\(currentUser\?\.is_federated\)/);
});
