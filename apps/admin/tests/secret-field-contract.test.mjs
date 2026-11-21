// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Secret fields in God Mode must not be unconditionally required.
 *
 * The API never returns an encrypted value — secrets are write-only — so every
 * secret field renders empty even when a secret is stored. A field marked
 * `required: true` therefore blocks the form until the operator fetches and
 * retypes a credential the instance already holds, just to change an unrelated
 * setting on the same page. An empty value is understood server-side as "keep
 * the existing secret", so there is nothing to gain by demanding it.
 *
 * All five OAuth and OIDC forms shipped that way while the email form did not.
 *
 * Nor may a secret field start with, or be reset to, a value from the server.
 * Whatever the configuration endpoint hands back for a secret key is at best a
 * mask, and submitting it again would overwrite the stored secret with it.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";

const AUTHENTICATION = new URL("../app/(all)/(dashboard)/authentication/", import.meta.url);
const EMAIL_FORM = new URL("../app/(all)/(dashboard)/email/email-config-form.tsx", import.meta.url);
const AI_FORM = new URL("../app/(all)/(dashboard)/ai/form.tsx", import.meta.url);
const SHARED_FORM_HOOK = new URL("../hooks/use-oauth-provider-config-form.ts", import.meta.url);

/** Every field literal declaring `type: "password"`, with its key. */
function passwordFields(source) {
  const fields = [];
  for (const match of source.matchAll(/key: "([A-Z0-9_]+)",\s*\n\s*type: "password",/g)) {
    const key = match[1];
    // The field literal runs to the next entry or the end of the array.
    const rest = source.slice(match.index);
    const end = rest.indexOf("\n    },");
    fields.push({ key, body: end === -1 ? rest : rest.slice(0, end) });
  }
  return fields;
}

function formSources() {
  const sources = [
    ["email-config-form.tsx", readFileSync(EMAIL_FORM, "utf8")],
    ["ai/form.tsx", readFileSync(AI_FORM, "utf8")],
  ];
  for (const entry of readdirSync(AUTHENTICATION, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    try {
      sources.push([entry.name, readFileSync(new URL(`${entry.name}/form.tsx`, AUTHENTICATION), "utf8")]);
    } catch {
      // Not every provider directory has a form; identity-import does not.
    }
  }
  return sources;
}

test("the panel has secret fields to check, so this test is looking at the right shape", () => {
  const found = formSources().flatMap(([, source]) => passwordFields(source));
  assert.ok(found.length >= 5, `expected the known secret fields, found ${found.length}`);
});

test("no secret field is required once its secret is stored", () => {
  const offenders = [];
  for (const [form, source] of formSources()) {
    for (const { key, body } of passwordFields(source)) {
      if (/required: true,/.test(body)) offenders.push(`${form}: ${key}`);
    }
  }

  assert.deepEqual(
    offenders,
    [],
    "these demand a secret the API will never show back, so changing any other " +
      `setting on the page means retyping a stored credential: ${offenders.join(", ")}`
  );
});

test("a secret that is not stored yet is still required", () => {
  const withoutGuard = [];
  for (const [form, source] of formSources()) {
    for (const { key, body } of passwordFields(source)) {
      // The email form predates the store flag and is left as it was.
      if (key === "EMAIL_HOST_PASSWORD") continue;
      if (!/required: !isSecretConfigured,/.test(body)) withoutGuard.push(`${form}: ${key}`);
    }
  }

  assert.deepEqual(
    withoutGuard,
    [],
    `these could be saved with no secret at all, leaving the provider unusable: ${withoutGuard.join(", ")}`
  );
});

test("no secret field is filled from the stored configuration", () => {
  const prefilled = [];
  for (const [form, source] of formSources()) {
    for (const { key } of passwordFields(source)) {
      if (new RegExp(`${key}: config\\[`).test(source)) prefilled.push(`${form}: ${key}`);
      if (!new RegExp(`${key}: "",`).test(source)) prefilled.push(`${form}: ${key} (no empty default)`);
    }
  }

  assert.deepEqual(prefilled, [], `these start from a value the server sent back: ${prefilled.join(", ")}`);
});

test("no form is reset with values from the save response", () => {
  const fromResponse = [];
  for (const [form, source] of [
    ...formSources(),
    ["use-oauth-provider-config-form.ts", readFileSync(SHARED_FORM_HOOK, "utf8")],
  ]) {
    if (/reset\([^;]*response/s.test(source)) fromResponse.push(form);
  }

  assert.deepEqual(fromResponse, [], `these refill the form from the response: ${fromResponse.join(", ")}`);
});

test("the shared provider form hook empties every secret it is given", () => {
  const hook = readFileSync(SHARED_FORM_HOOK, "utf8");
  // Both the initial values and the values after a save go through the same filter.
  assert.match(hook, /useForm<T>\(\{ defaultValues: withEmptySecrets\(defaultValues, secretKeys\) \}\)/);
  assert.match(hook, /form\.reset\(withEmptySecrets\(formData, secretKeys\)\)/);
  assert.match(hook, /for \(const key of secretKeys\) next\[key\] = "";/);
});

test("every provider form built on the shared hook names its secret", () => {
  const missing = [];
  for (const [form, source] of formSources()) {
    if (!source.includes("useOAuthProviderConfigForm<")) continue;
    for (const { key } of passwordFields(source)) {
      if (!new RegExp(`\\[\\s*"${key}"\\s*\\]`).test(source)) missing.push(`${form}: ${key}`);
    }
  }

  assert.deepEqual(missing, [], `the hook would keep these secrets after a save: ${missing.join(", ")}`);
});

// A browser offers a saved login to any empty password field it is allowed to
// fill. Accepted into a secret field, that login would be saved over the stored
// secret on the next save. "new-password" is the token browsers honour for
// password fields ("off" is ignored there), so every secret renders with it.
const CONTROLLER_INPUT = new URL("../components/common/controller-input.tsx", import.meta.url);

test("secret fields render with autocomplete new-password", () => {
  const input = readFileSync(CONTROLLER_INPUT, "utf8");
  assert.match(input, /autoComplete=\{type === "password" \? "new-password" : undefined\}/);
  // The prop has to reach the rendered InputField, not a wrapper around it.
  const field = input.slice(input.indexOf("<InputField"), input.indexOf("/>", input.indexOf("endIcon=")));
  assert.match(field, /autoComplete=/);
});

test("secret fields are only rendered through ControllerInput", () => {
  const direct = [];
  for (const [form, source] of formSources()) {
    // The identity import asks for the administrator's own password to confirm
    // the import; that is a login, filled as the current password, not a secret.
    const withoutReauth = source.replace(/type="password"\s*\n\s*autoComplete="current-password"/g, "");
    if (/type="password"|type=\{[^}]*"password"/.test(withoutReauth)) direct.push(form);
  }

  assert.deepEqual(direct, [], `these render a password input outside ControllerInput: ${direct.join(", ")}`);
});
