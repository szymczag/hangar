// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Every second-factor error the API can return must render in God Mode.
 *
 * The API answers with a numeric code and the console maps it to copy. A code
 * added on one side only reaches the operator as "Something went wrong", which
 * for ADMIN_2FA_CREDENTIAL_DISABLED would hide the one thing they need to know:
 * that the console stays locked until a shell reset. That message must also
 * name the management command that actually exists.
 */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const ROOT = new URL("../../../", import.meta.url);
const read = (path) => readFileSync(new URL(path, ROOT), "utf8");

const API_ERRORS = read("apps/api/plane/authentication/adapter/error.py");
const CONSTANTS = read("packages/constants/src/auth/index.ts");
const HELPERS = read("apps/admin/app/(all)/(home)/auth-helpers.tsx");

function apiSecondFactorCodes() {
  return [...API_ERRORS.matchAll(/"(ADMIN_2FA_[A-Z_]+)": (\d+),/g)].map(([, name, code]) => ({ name, code }));
}

function adminEnum() {
  const start = CONSTANTS.indexOf("export enum EAdminAuthErrorCodes");
  const body = CONSTANTS.slice(start, CONSTANTS.indexOf("}", start));
  return new Map([...body.matchAll(/(ADMIN_2FA_[A-Z_]+) = "(\d+)"/g)].map(([, name, code]) => [name, code]));
}

test("the API defines second-factor codes", () => {
  assert.ok(apiSecondFactorCodes().some(({ name }) => name === "ADMIN_2FA_CREDENTIAL_DISABLED"));
});

test("every second-factor code has the same number in the admin enum", () => {
  const enumCodes = adminEnum();
  for (const { name, code } of apiSecondFactorCodes()) {
    assert.equal(enumCodes.get(name), code, `${name} is ${code} in the API`);
  }
});

test("every second-factor code has a message and is shown as a banner", () => {
  for (const { name } of apiSecondFactorCodes()) {
    const uses = HELPERS.split(`EAdminAuthErrorCodes.${name}]`).length - 1;
    assert.equal(uses, 1, `${name} needs one entry in errorCodeMessages`);
    assert.match(HELPERS, new RegExp(`EAdminAuthErrorCodes\\.${name},`), `${name} must be a banner code`);
  }
});

test("the disabled-key message names the real reset command", () => {
  const entry = HELPERS.slice(HELPERS.indexOf("EAdminAuthErrorCodes.ADMIN_2FA_CREDENTIAL_DISABLED]"));
  const command = entry.match(/manage\.py ([a-z_0-9]+)/);
  assert.ok(command, "the message must say which command resets the key");
  assert.ok(
    existsSync(new URL(`apps/api/plane/ext/management/commands/${command[1]}.py`, ROOT)),
    `${command[1]} is not a management command`
  );
});
