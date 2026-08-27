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
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";

const AUTHENTICATION = new URL("../app/(all)/(dashboard)/authentication/", import.meta.url);
const EMAIL_FORM = new URL("../app/(all)/(dashboard)/email/email-config-form.tsx", import.meta.url);

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
  const sources = [["email-config-form.tsx", readFileSync(EMAIL_FORM, "utf8")]];
  for (const entry of readdirSync(AUTHENTICATION, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    try {
      sources.push([entry.name, readFileSync(new URL(`${entry.name}/form.tsx`, AUTHENTICATION), "utf8")]);
    } catch {
      // Not every provider directory has a form; saml and domains do not.
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
