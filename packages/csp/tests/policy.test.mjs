/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";

import {
  buildContentSecurityPolicy,
  hashSource,
  inlineScriptHashes,
  policyHeaderName,
  runtimeSourcesFromEnv,
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
  assert.equal(
    directive(policy, "img-src"),
    "'self' blob: data: https://*.googleusercontent.com https://avatars.githubusercontent.com https://images.unsplash.com https://images.example"
  );
  assert.equal(directive(policy, "connect-src"), "'self' https://cdn.jsdelivr.net https://storage.example");
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

test("runtime sources come from the environment and default to self", () => {
  assert.deepEqual(runtimeSourcesFromEnv({}), {
    imgSrc: "",
    connectSrc: "",
    mediaSrc: "",
    frameSrc: "",
    formAction: "",
    reportUri: "/api/csp-report/",
  });
  // This release observes before it enforces; see DEFAULT_REPORT_ONLY.
  assert.equal(policyHeaderName({}), "Content-Security-Policy-Report-Only");
  assert.equal(policyHeaderName({ HANGAR_CSP_REPORT_ONLY: "false" }), "Content-Security-Policy");
  assert.equal(policyHeaderName({ HANGAR_CSP_REPORT_ONLY: "true" }), "Content-Security-Policy-Report-Only");
});
