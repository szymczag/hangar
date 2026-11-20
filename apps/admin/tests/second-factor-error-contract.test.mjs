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

// The disabled-key message is a command an operator pastes into a shell on the
// server, so the address in it must be theirs and must not be able to carry
// anything else. The address reaches the console through the sign-in redirect,
// which anyone can craft as a link.
const SIGN_IN_FORM = read("apps/admin/app/(all)/(home)/sign-in-form.tsx");
const BANNER = read("apps/admin/app/(all)/(home)/auth-banner.tsx");
const ADMIN_VIEW = read("apps/api/plane/license/api/views/admin.py");

function resetCommandEmail() {
  const pattern = HELPERS.match(/const RESET_COMMAND_EMAIL = \/(.+)\/;\n/);
  assert.ok(pattern, "the address filter must be a single regular expression literal");
  const regex = new RegExp(pattern[1]);
  return (email) => (email && email.length <= 254 && regex.test(email) ? email : "<your email>");
}

test("the API sends the account's address with the disabled-key code", () => {
  const start = ADMIN_VIEW.indexOf('AUTHENTICATION_ERROR_CODES["ADMIN_2FA_CREDENTIAL_DISABLED"]');
  assert.notEqual(start, -1);
  const call = ADMIN_VIEW.slice(start, ADMIN_VIEW.indexOf(")", start));
  assert.match(call, /payload=\{"email": user\.email\}/);
});

test("the sign-in form passes the redirect's address to the error copy", () => {
  assert.match(SIGN_IN_FORM, /authErrorHandler\(errorCode\?\.toString\(\) as EAdminAuthErrorCodes, emailParam\)/);
  assert.match(SIGN_IN_FORM, /\}, \[errorCode, emailParam\]\);/);
});

test("the disabled-key message prints the address only through the filter", () => {
  const entry = HELPERS.slice(HELPERS.indexOf("EAdminAuthErrorCodes.ADMIN_2FA_CREDENTIAL_DISABLED]"));
  const message = entry.slice(0, entry.indexOf("},"));
  assert.match(message, /--email \$\{resetCommandEmail\(email\)\}/);
  assert.doesNotMatch(message, /\$\{email/);
});

test("a plain address is printed and anything shell-like keeps the placeholder", () => {
  const filter = resetCommandEmail();
  for (const email of ["admin@corp.com", "first.last+ops@mail.example.co.uk", "a_b-c@x-y.io"]) {
    assert.equal(filter(email), email);
  }
  for (const email of [
    undefined,
    "",
    "admin",
    "admin@corp.com; rm -rf /",
    "$(id)@corp.com",
    "`id`@corp.com",
    "admin@corp.com && curl x",
    "a'b@corp.com",
    'a"b@corp.com',
    "a b@corp.com",
    "admin@corp.com\nid",
    "admin@corp.com|id",
    "-rf@corp.com",
    "admin@corp",
    `${"a".repeat(65)}@corp.com`,
  ]) {
    assert.equal(filter(email), "<your email>", JSON.stringify(email));
  }
});

test("the banner shows second-factor titles", () => {
  assert.match(BANNER, /showsBannerTitle\(bannerData\.code\) && <p[^>]*>\{bannerData\.title\}<\/p>/);
  const codes = HELPERS.slice(HELPERS.indexOf("const SECOND_FACTOR_CODES"));
  assert.match(codes.slice(0, codes.indexOf("];")), /EAdminAuthErrorCodes\.ADMIN_2FA_CREDENTIAL_DISABLED,/);
});
