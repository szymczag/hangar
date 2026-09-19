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
  trustedTypesModeFromDocument,
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

test("enforcing, the default policy returns what the sanitizer returns and reports the change", () => {
  withBrowser();
  const sent = [];
  installTrustedTypesPolicies({
    mode: "enforce",
    sanitize: (value) => value.replace(" onclick=x", ""),
    send: (url, body) => sent.push(JSON.parse(body)["csp-report"]),
  });
  const policy = policies.get("default");
  assert.equal(policy.rules.createHTML("<p onclick=x>a</p>", "TrustedHTML", "Element innerHTML"), "<p>a</p>");
  assert.equal(policy.rules.createHTML("<p>fine</p>", "TrustedHTML", "Element innerHTML"), "<p>fine</p>");
  assert.deepEqual(
    sent.map((report) => [report["violated-directive"], report.disposition]),
    [["html-changed", "enforce"]]
  );
});

test("enforcing, script text and cross-origin script URLs are refused", () => {
  withBrowser();
  const sent = [];
  installTrustedTypesPolicies({ mode: "enforce", send: (url, body) => sent.push(JSON.parse(body)["csp-report"]) });
  const policy = policies.get("default");
  assert.equal(policy.rules.createScript("alert(1)", "TrustedScript", "HTMLScriptElement text"), undefined);
  assert.equal(
    policy.rules.createScriptURL("https://evil.example/x.js", "TrustedScriptURL", "HTMLScriptElement src"),
    undefined
  );
  assert.equal(
    policy.rules.createScriptURL("/assets/chunk.js", "TrustedScriptURL", "HTMLScriptElement src"),
    "/assets/chunk.js"
  );
  assert.deepEqual(
    sent.map((report) => report["violated-directive"]),
    ["script", "script-url"]
  );
});

test("enforcing, a failing sanitizer fails closed and a known library script passes", () => {
  withBrowser();
  installTrustedTypesPolicies({
    mode: "enforce",
    sanitize: () => {
      throw new Error("boom");
    },
    send: () => {},
  });
  const policy = policies.get("default");
  assert.equal(policy.rules.createHTML("<p>a</p>", "TrustedHTML", "Element innerHTML"), "");
  const script =
    '((e,t)=>{let n=document.documentElement,r=["light","dark"];try{localStorage.getItem(e)}catch{}' +
    'matchMedia("(prefers-color-scheme: dark)")})("theme")';
  assert.ok(KNOWN_LIBRARY_SCRIPTS.some((known) => known.matches(script)));
  assert.equal(policy.rules.createHTML(script, "TrustedHTML", "Element innerHTML"), script);
});

/** A document whose meta tag (in the head or the body) says `content`. */
const documentWith = (content, where = "head") => {
  const meta = { getAttribute: () => content };
  const scope = { querySelector: (selector) => (selector.includes("hangar-trusted-types") ? meta : null) };
  return where === "head" ? { head: scope } : { head: { querySelector: () => null }, body: scope };
};

test("the mode comes from the document's head, and anything unknown means report", () => {
  assert.equal(trustedTypesModeFromDocument(documentWith("enforce")), "enforce");
  assert.equal(trustedTypesModeFromDocument(documentWith("off")), "off");
  assert.equal(trustedTypesModeFromDocument(documentWith("sanitize")), "report");
  // Markup in the body cannot choose the mode.
  assert.equal(trustedTypesModeFromDocument(documentWith("off", "body")), "report");
  assert.equal(trustedTypesModeFromDocument(undefined), "report");
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
