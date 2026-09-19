/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

import { TRUSTED_TYPES_MEASUREMENT } from "../src/index.mjs";

const here = new URL("..", import.meta.url).pathname;

test("the start-up hook measures the same Trusted Types policy as @plane/csp", () => {
  const hook = readFileSync(join(here, "nginx/15-hangar-csp.envsh"), "utf8");
  assert.ok(hook.includes(`"${TRUSTED_TYPES_MEASUREMENT}\${HANGAR_CSP_REPORT}"`));
});

const hookValue = (variable, env) =>
  execFileSync(
    "sh",
    ["-c", `mkdir() { :; }; . "${join(here, "nginx/15-hangar-csp.envsh")}"; printf %s "$${variable}"`],
    { env: { PATH: process.env.PATH, ...env }, encoding: "utf8" }
  );

test("the hook's Trusted Types value follows HANGAR_CSP_TRUSTED_TYPES", () => {
  const value = (env) => hookValue("HANGAR_CSP_TRUSTED_TYPES_POLICY", env);
  assert.equal(value({}), `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`);
  assert.equal(value({ HANGAR_CSP_REPORT_URI: "" }), TRUSTED_TYPES_MEASUREMENT);
  assert.equal(value({ HANGAR_CSP_TRUSTED_TYPES: "off" }), "");
  // Enforcing the main policy must not enforce this one.
  assert.equal(value({ HANGAR_CSP_REPORT_ONLY: "false" }), `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`);
});

test("the hook's Trusted Types header and page mode follow HANGAR_CSP_TRUSTED_TYPES only", () => {
  const header = (env) => hookValue("HANGAR_CSP_TRUSTED_TYPES_HEADER", env);
  const mode = (env) => hookValue("HANGAR_CSP_TRUSTED_TYPES_MODE", env);
  assert.equal(header({}), "Content-Security-Policy-Report-Only");
  assert.equal(mode({}), "report");
  assert.equal(header({ HANGAR_CSP_TRUSTED_TYPES: "enforce" }), "Content-Security-Policy");
  assert.equal(mode({ HANGAR_CSP_TRUSTED_TYPES: "enforce" }), "enforce");
  assert.equal(
    hookValue("HANGAR_CSP_TRUSTED_TYPES_POLICY", { HANGAR_CSP_TRUSTED_TYPES: "enforce" }),
    `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`
  );
  assert.equal(mode({ HANGAR_CSP_TRUSTED_TYPES: "off" }), "off");
  // A typo reports; it neither enforces nor stops measuring.
  assert.equal(mode({ HANGAR_CSP_TRUSTED_TYPES: "Enforce" }), "report");
  assert.equal(header({ HANGAR_CSP_TRUSTED_TYPES: "Enforce" }), "Content-Security-Policy-Report-Only");
  // Enforcing the main policy does not enforce Trusted Types.
  assert.equal(header({ HANGAR_CSP_REPORT_ONLY: "false" }), "Content-Security-Policy-Report-Only");
});

const generate = (html) => {
  const dir = mkdtempSync(join(tmpdir(), "hangar-csp-"));
  writeFileSync(join(dir, "index.html"), html);
  execFileSync(
    process.execPath,
    [join(here, "bin/nginx-headers.mjs"), "--html", join(dir, "index.html"), "--out", join(dir, "out.template")],
    { stdio: "pipe" }
  );
  return readFileSync(join(dir, "out.template"), "utf8");
};

const BUILT_HTML =
  '<head><meta name="hangar-trusted-types" content="report"/></head>' +
  '<script>window.x = 1;</script><script type="module">import "/a.js";</script>';

test("the generated template refuses a page that cannot be told the Trusted Types mode", () => {
  assert.throws(() => generate("<script>window.x = 1;</script>"), /hangar-trusted-types/);
});

test("the generated template sends Trusted Types as its own header and tells the page its mode", () => {
  const template = generate(BUILT_HTML);
  assert.match(
    template,
    /add_header \$\{HANGAR_CSP_TRUSTED_TYPES_HEADER\} "\$\{HANGAR_CSP_TRUSTED_TYPES_POLICY\}" always;/
  );
  assert.ok(
    template.includes(
      `sub_filter '<meta name="hangar-trusted-types" content="report"' '<meta name="hangar-trusted-types" content="\${HANGAR_CSP_TRUSTED_TYPES_MODE}"';`
    )
  );
});

test("the generated template keeps Trusted Types out of the main policy", () => {
  const template = generate(BUILT_HTML);
  assert.doesNotMatch(
    template.split("\n").find((line) => line.includes("${HANGAR_CSP_HEADER}")),
    /trusted-types/
  );
});
