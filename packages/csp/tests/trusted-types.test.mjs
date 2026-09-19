/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";

import { TRUSTED_TYPES_MEASUREMENT } from "../src/index.mjs";

import {
  KNOWN_LIBRARY_SCRIPTS,
  OBSERVE_MAX_LENGTH,
  TRUSTED_TYPES_POLICY_NAMES,
  inertHTML,
  installTrustedTypesPolicies,
} from "../src/trusted-types.mjs";

// A stand-in for the browser: records the policies created, and a DOMParser
// whose serialization is the input itself, so "canonical" == value in tests.
const policies = new Map();
const fakeTrustedTypes = {
  createPolicy(name, rules) {
    if (policies.has(name)) throw new TypeError(`duplicate policy ${name}`);
    const policy = {
      name,
      createHTML: (value, ...rest) => ({ trusted: "html", value: rules.createHTML(value, ...rest) }),
      createScript: (value, ...rest) => rules.createScript?.(value, ...rest),
      createScriptURL: (value, ...rest) => rules.createScriptURL?.(value, ...rest),
      rules,
    };
    policies.set(name, policy);
    return policy;
  },
};

const clean = () => {
  policies.clear();
  for (const key of Object.getOwnPropertySymbols(globalThis)) {
    if (String(key.description).startsWith("hangar.trusted-types")) delete globalThis[key];
  }
  delete globalThis.trustedTypes;
  delete globalThis.DOMParser;
  delete globalThis.location;
  delete globalThis.document;
};

beforeEach(clean);
afterEach(clean);

const withBrowser = () => {
  globalThis.trustedTypes = fakeTrustedTypes;
  globalThis.DOMParser = class {
    parseFromString(input) {
      return { body: { innerHTML: typeof input === "string" ? input : input.value } };
    }
  };
  globalThis.location = { href: "https://hangar.example/ws/", origin: "https://hangar.example" };
};

test("the header allows exactly the policies this module creates, plus DOMPurify's own", () => {
  assert.deepEqual(TRUSTED_TYPES_POLICY_NAMES, ["hangar-inert", "default", "dompurify"]);
  assert.ok(TRUSTED_TYPES_MEASUREMENT.endsWith(`trusted-types ${TRUSTED_TYPES_POLICY_NAMES.join(" ")}`));
});

test("without Trusted Types nothing is created and strings pass through", () => {
  assert.equal(inertHTML("<p>x</p>"), "<p>x</p>");
  assert.equal(installTrustedTypesPolicies(), false);
});

test("inertHTML goes through one hangar-inert policy and leaves the value unchanged", () => {
  withBrowser();
  const first = inertHTML("<img src=x onerror=alert(1)>");
  const second = inertHTML("<p>y</p>");
  assert.deepEqual(first, { trusted: "html", value: "<img src=x onerror=alert(1)>" });
  assert.deepEqual(second, { trusted: "html", value: "<p>y</p>" });
  assert.deepEqual([...policies.keys()], ["hangar-inert"]);
});

test("the default policy observes: it returns every value unchanged", () => {
  withBrowser();
  const sent = [];
  installTrustedTypesPolicies({
    sanitize: () => "<p>changed</p>",
    send: (url, body) => sent.push([url, JSON.parse(body)]),
  });
  const policy = policies.get("default");

  assert.equal(policy.rules.createHTML("<p onclick=x>a</p>", "TrustedHTML", "Element innerHTML"), "<p onclick=x>a</p>");
  assert.equal(policy.rules.createScript("alert(1)", "TrustedScript", "HTMLScriptElement text"), "alert(1)");
  assert.equal(
    policy.rules.createScriptURL("https://evil.example/x.js", "TrustedScriptURL", "HTMLScriptElement src"),
    "https://evil.example/x.js"
  );

  const findings = sent.map(([, body]) => body["csp-report"]["violated-directive"]);
  assert.deepEqual(findings, ["html-would-change", "script", "script-url"]);
  assert.equal(sent[0][0], "/api/csp-report/");
  assert.equal(sent[0][1]["csp-report"].disposition, "observe");
  assert.equal(sent[0][1]["csp-report"]["blocked-uri"], "Element innerHTML");
});

test("nothing is reported when the sanitizer would not change the value", () => {
  withBrowser();
  const sent = [];
  installTrustedTypesPolicies({ sanitize: (value) => value, send: (url, body) => sent.push(body) });
  const policy = policies.get("default");
  policy.rules.createHTML("<p>fine</p>", "TrustedHTML", "DOMParser parseFromString");
  policy.rules.createScriptURL("/assets/chunk.js", "TrustedScriptURL", "HTMLScriptElement src");
  assert.deepEqual(sent, []);
});

test("a finding is reported once per page, and oversized values are not compared", () => {
  withBrowser();
  const sent = [];
  let compared = 0;
  installTrustedTypesPolicies({
    sanitize: () => {
      compared += 1;
      return "";
    },
    send: (url, body) => sent.push(body),
  });
  const policy = policies.get("default");
  policy.rules.createHTML("<p>same</p>", "TrustedHTML", "Element innerHTML");
  policy.rules.createHTML("<p>same</p>", "TrustedHTML", "Element innerHTML");
  policy.rules.createHTML("x".repeat(OBSERVE_MAX_LENGTH + 1), "TrustedHTML", "Element innerHTML");
  assert.equal(sent.length, 1);
  assert.equal(compared, 2);
});

test("a failing sanitizer or transport never breaks the sink", () => {
  withBrowser();
  installTrustedTypesPolicies({
    sanitize: () => {
      throw new Error("boom");
    },
    send: () => {
      throw new Error("offline");
    },
  });
  assert.equal(policies.get("default").rules.createHTML("<p>a</p>", "TrustedHTML", "Element innerHTML"), "<p>a</p>");
});

test("installing twice, or over an existing default policy, does not throw", () => {
  withBrowser();
  assert.equal(installTrustedTypesPolicies({ send: () => {} }), true);
  assert.equal(installTrustedTypesPolicies({ send: () => {} }), false);
  clean();
  withBrowser();
  fakeTrustedTypes.createPolicy("default", { createHTML: (value) => value });
  assert.equal(installTrustedTypesPolicies({ send: () => {} }), false);
});

test("a served inline script rendered again is recognised, not compared as HTML", () => {
  withBrowser();
  globalThis.document = {
    scripts: [
      { src: "", textContent: "((e)=>{if(a<b)x()})(1)" },
      { src: "/config.js", textContent: "" },
    ],
  };
  const sent = [];
  installTrustedTypesPolicies({ sanitize: () => "", send: (url, body) => sent.push(JSON.parse(body)) });
  const policy = policies.get("default");
  policy.rules.createHTML("((e)=>{if(a<b)x()})(1)", "TrustedHTML", "Element innerHTML");
  assert.deepEqual(sent, []);
  // A direct call (ProseMirror passes no sink) is still observed, and named.
  policy.rules.createHTML("<img src=x onerror=y>", "TrustedHTML");
  assert.equal(sent[0]["csp-report"]["blocked-uri"], "direct call");
});

test("next-themes' script is recognised in the served and in the client-rendered minification", async () => {
  const { readFileSync, existsSync } = await import("node:fs");
  const nextThemes = KNOWN_LIBRARY_SCRIPTS.find((script) => script.name === "next-themes");
  // The copy React renders on the client (minified by the app bundler).
  const client =
    "((e,t,n,r,i,a,o,s)=>{let c=document.documentElement,l=[`light`,`dark`];function u(t){c.setAttribute(e,t)}" +
    "try{let e=localStorage.getItem(t)||n;u(e)}catch(e){}window.matchMedia(`(prefers-color-scheme: dark)`)})(1)";
  assert.ok(nextThemes.matches(client));
  // The copy served in the built index.html, when a build is present.
  const index = new URL("../../../apps/web/build/client/index.html", import.meta.url);
  if (existsSync(index)) {
    const html = readFileSync(index, "utf8");
    const served = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)]
      .filter((match) => !/\bsrc=/.test(match[1]))
      .map((match) => match[2])
      .find((body) => body.includes("document.documentElement"));
    assert.ok(served && nextThemes.matches(served));
  }
  // Markup is not mistaken for it.
  assert.equal(
    nextThemes.matches("<p>document.documentElement localStorage.getItem( prefers-color-scheme: dark</p>"),
    false
  );
});
