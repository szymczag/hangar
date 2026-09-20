/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";

import {
  APP_SOURCES,
  TRUSTED_TYPES_MEASUREMENT,
  buildContentSecurityPolicy,
  hashSource,
  inlineScriptHashes,
  policyHeaderName,
  runtimeSourcesFromEnv,
  trustedTypesHeaderName,
  trustedTypesModeFromEnv,
  trustedTypesReportPolicy,
} from "../src/index.mjs";

const directive = (policy, name) =>
  policy
    .split("; ")
    .find((part) => part.startsWith(`${name} `))
    ?.slice(name.length + 1);

test("the policy never relaxes to unsafe sources", () => {
  const policy = buildContentSecurityPolicy({
    scriptSources: ["'sha256-abc'"],
    imgSrc: "https://images.example",
    connectSrc: "https://storage.example",
  });
  assert.doesNotMatch(policy, /unsafe/);
  assert.equal(directive(policy, "script-src"), "'self' 'sha256-abc'");
  assert.equal(directive(policy, "script-src-attr"), "'none'");
  assert.equal(directive(policy, "style-src-attr"), "'none'");
  assert.equal(directive(policy, "object-src"), "'none'");
  assert.equal(directive(policy, "frame-ancestors"), "'none'");
  assert.equal(directive(policy, "frame-src"), "'none'");
  assert.equal(directive(policy, "img-src"), "'self' blob: data: https://images.example");
  assert.equal(directive(policy, "connect-src"), "'self' https://storage.example");
});

test("nothing is fetched from another host unless the deployment adds one", () => {
  assert.deepEqual(APP_SOURCES, { connectSrc: [], imgSrc: [] });
  assert.equal(directive(buildContentSecurityPolicy(), "img-src"), "'self' blob: data:");
  assert.equal(directive(buildContentSecurityPolicy(), "connect-src"), "'self'");
});

test("inline scripts are hashed exactly, external ones are skipped", () => {
  const html =
    '<script src="/config.js"></script><script>window.__ctx = {"a":1};</script>' +
    '<script type="module" async="">import "/assets/x.js";</script>';
  const hashes = inlineScriptHashes(html);
  const expected = (body) => `'sha256-${createHash("sha256").update(body).digest("base64")}'`;
  assert.deepEqual(hashes, [expected('window.__ctx = {"a":1};'), expected('import "/assets/x.js";')]);
  assert.equal(hashSource("x"), expected("x"));
});

test("an inline script ends where the parser ends it, and a crafted document does not stall", () => {
  // `</script` ends a script however it continues.
  assert.deepEqual(inlineScriptHashes("<script>one</script\t\n foo>"), [hashSource("one")]);
  // A document made of end-tag prefixes has no script to hash and returns at once.
  const started = Date.now();
  assert.deepEqual(inlineScriptHashes(`<script>${"</scri".repeat(50_000)}`), []);
  assert.ok(Date.now() - started < 1_000);
});

test("runtime sources come from the environment and default to self", () => {
  assert.deepEqual(runtimeSourcesFromEnv({}), {
    imgSrc: "",
    connectSrc: "",
    mediaSrc: "",
    frameSrc: "",
    formAction: "",
    reportUri: "/api/csp-report/",
  });
  // Enforced unless a deployment asks to only report; see DEFAULT_REPORT_ONLY.
  assert.equal(policyHeaderName({}), "Content-Security-Policy");
  assert.equal(policyHeaderName({ HANGAR_CSP_REPORT_ONLY: "false" }), "Content-Security-Policy");
  assert.equal(policyHeaderName({ HANGAR_CSP_REPORT_ONLY: "true" }), "Content-Security-Policy-Report-Only");
});

test("Trusted Types is measured in a policy of its own and can be switched off", () => {
  // Kept out of the main policy: enforcing that must not start enforcing this.
  assert.doesNotMatch(buildContentSecurityPolicy(), /trusted-types/);
  assert.equal(
    TRUSTED_TYPES_MEASUREMENT,
    "require-trusted-types-for 'script'; trusted-types hangar-inert default dompurify"
  );
  assert.equal(
    trustedTypesReportPolicy({ reportUri: "/api/csp-report/" }),
    `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`
  );
  assert.equal(trustedTypesReportPolicy({ mode: "off", reportUri: "/api/csp-report/" }), "");
  assert.equal(trustedTypesModeFromEnv({}), "report");
  assert.equal(trustedTypesModeFromEnv({ HANGAR_CSP_TRUSTED_TYPES: "off" }), "off");
  assert.equal(trustedTypesModeFromEnv({ HANGAR_CSP_TRUSTED_TYPES: "enforce" }), "enforce");
  // A typo must not enforce, nor switch measuring off.
  assert.equal(trustedTypesModeFromEnv({ HANGAR_CSP_TRUSTED_TYPES: "enforced" }), "report");
  assert.equal(trustedTypesHeaderName("report"), "Content-Security-Policy-Report-Only");
  assert.equal(trustedTypesHeaderName("enforce"), "Content-Security-Policy");
  assert.equal(
    trustedTypesReportPolicy({ mode: "enforce", reportUri: "/api/csp-report/" }),
    `${TRUSTED_TYPES_MEASUREMENT}; report-uri /api/csp-report/`
  );
});
