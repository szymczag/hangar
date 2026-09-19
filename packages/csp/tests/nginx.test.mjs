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

test("the hook's Trusted Types value follows HANGAR_CSP_TRUSTED_TYPES", () => {
  const value = (env) =>
    execFileSync(
      "sh",
      [
        "-c",
        `mkdir() { :; }; . "${join(here, "nginx/15-hangar-csp.envsh")}"; printf %s "$HANGAR_CSP_TRUSTED_TYPES_POLICY"`,
      ],
      { env: { PATH: process.env.PATH, ...env }, encoding: "utf8" }
    );
  assert.equal(value({}), `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`);
  assert.equal(value({ HANGAR_CSP_REPORT_URI: "" }), TRUSTED_TYPES_MEASUREMENT);
  assert.equal(value({ HANGAR_CSP_TRUSTED_TYPES: "off" }), "");
  // Enforcing the main policy must not enforce this one.
  assert.equal(value({ HANGAR_CSP_REPORT_ONLY: "false" }), `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`);
});

test("the generated template sends Trusted Types as its own report-only header", () => {
  const dir = mkdtempSync(join(tmpdir(), "hangar-csp-"));
  writeFileSync(
    join(dir, "index.html"),
    '<script>window.x = 1;</script><script type="module">import "/a.js";</script>'
  );
  execFileSync(process.execPath, [
    join(here, "bin/nginx-headers.mjs"),
    "--html",
    join(dir, "index.html"),
    "--out",
    join(dir, "out.template"),
  ]);
  const template = readFileSync(join(dir, "out.template"), "utf8");
  assert.doesNotMatch(
    template.split("\n").find((line) => line.includes("${HANGAR_CSP_HEADER}")),
    /trusted-types/
  );
  assert.match(
    template,
    /add_header Content-Security-Policy-Report-Only "\$\{HANGAR_CSP_TRUSTED_TYPES_POLICY\}" always;/
  );
});
