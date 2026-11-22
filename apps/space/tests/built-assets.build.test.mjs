// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Checks on the built published-boards app, run after `react-router build`
 * (CI runs them after the Trusted Types bundle check). Space is the one
 * frontend rendered on the server, so its Content-Security-Policy is a
 * per-request nonce rather than build-time hashes; these read what the built
 * server actually sends.
 *
 * - Propel's variants need Tailwind 4.2 utilities (`inset-e-4`, ...); Tailwind
 *   drops a class it does not know without a warning (see the God Mode test).
 * - Every inline script in the served HTML carries that response's nonce, no
 *   inline style can be refused, and the page renders through
 *   `TranslationProvider` on the server (entry.server.tsx waits for i18n), so
 *   the client's first render, after entry.client.tsx waits for the same, matches it.
 * - Base UI's PrehydrationScript, the one inline script Propel can emit during
 *   server rendering, takes the nonce from `CSPProvider`, which providers.tsx
 *   mounts with the request's nonce.
 *
 *   pnpm turbo run build --filter=space && pnpm test:space-build
 */

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

import { builtCss, missingVariantClasses } from "../../../scripts/propel/built-css.mjs";

const SPACE = new URL("../", import.meta.url);

test("every utility in the Propel variants has a rule in the built space CSS", () => {
  assert.deepEqual(
    missingVariantClasses("space"),
    [],
    "Tailwind generated no rule for these classes; is the catalog too old?"
  );
});

test("the toast's logical insets are in the built space CSS", () => {
  const css = builtCss("space");
  for (const utility of ["inset-e-4", "inset-e-0", "inset-s-0", "inset-e-2"]) {
    assert.match(css, new RegExp(`\\.${utility}\\{inset-inline-(end|start):`), utility);
  }
});

const attribute = (tag, name) => new RegExp(`\\s${name}="([^"]*)"`, "i").exec(tag)?.[1];

async function render(path) {
  const { createRequestHandler } = await import("react-router");
  const build = await import(new URL("build/server/index.js", SPACE).href);
  const handler = createRequestHandler(build, "production");
  const base = (build.basename ?? "/").replace(/\/$/, "");
  const response = await handler(new Request(`http://localhost${base}${path}`));
  return { response, html: await response.text() };
}

const nonceOf = (policy) => /'nonce-([^']+)'/.exec(policy)?.[1];

test("a published board's HTML carries the response's nonce on every inline script", async () => {
  const { response, html } = await render("/issues/0123456789abcdef0123456789abcdef");
  assert.equal(response.status, 200);
  const policy = response.headers.get("content-security-policy");
  assert.ok(policy, "space sends an enforced policy");
  assert.doesNotMatch(policy, /unsafe-inline|unsafe-eval/);
  assert.match(policy, /style-src-attr 'none'/);
  const nonce = nonceOf(policy);
  assert.ok(nonce, "the policy allows scripts by nonce");

  const scripts = [...html.matchAll(/<script\b[^>]*>/gi)].map(([tag]) => tag);
  const inline = scripts.filter((tag) => attribute(tag, "src") === undefined);
  assert.ok(inline.length > 0, "React Router inlines its context and the hydration entry");
  for (const tag of inline) assert.equal(attribute(tag, "nonce"), nonce, tag);
  for (const external of scripts.filter((tag) => attribute(tag, "src") !== undefined)) {
    // External scripts are allowed by 'self': this origin only.
    assert.match(attribute(external, "src"), /^\/(?!\/)/, external);
  }

  // style-src-elem allows only 'self' and the hashes of RUNTIME_STYLE_ELEMENTS.
  const allowedStyles = new Set([...policy.matchAll(/'sha256-([^']+)'/g)].map(([, hash]) => hash));
  for (const [, body] of html.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style\b[^>]*>/gi)) {
    assert.ok(allowedStyles.has(createHash("sha256").update(body, "utf8").digest("base64")), body);
  }
  // style-src-attr 'none' and script-src-attr 'none': nothing inline on an element.
  assert.doesNotMatch(html, /<[^>]+\sstyle\s*=/i);
  assert.doesNotMatch(html, /<[^>]+\son[a-z]+\s*=/i);

  // The providers rendered on the server: the instance loader sits inside
  // TranslationProvider, which renders nothing until i18n is ready.
  const body = html.slice(html.indexOf("<body"));
  assert.match(body, /<img src="[^"]*\/assets\/logo-loader-[^"]+\.png" alt="Hangar"/);
});

test("each response gets a nonce of its own", async () => {
  const first = nonceOf((await render("/")).response.headers.get("content-security-policy"));
  const second = nonceOf((await render("/")).response.headers.get("content-security-policy"));
  assert.ok(first && second);
  assert.notEqual(first, second);
});

test("providers.tsx hands the request's nonce to Base UI through CSPProvider", () => {
  const source = readFileSync(new URL("app/providers.tsx", SPACE), "utf8");
  assert.match(source, /import \{ CSPProvider \} from "@makeplane\/propel\/components\/csp-provider";/);
  assert.match(source, /const nonce = useContext\(UNSAFE_FrameworkContext\)\?\.nonce;/);
  assert.match(source, /<CSPProvider nonce=\{nonce\}>/);
});

test("Base UI's PrehydrationScript takes its nonce from Propel's CSPProvider", async () => {
  // Propel's own Tabs, so the indicator and the provider share Propel's single
  // @base-ui/react copy, as they do in the app. No Propel or blocks component
  // passes renderBeforeHydration today; the indicator is told to here so the
  // script is rendered at all.
  const { createElement: h } = await import("react");
  const { renderToString } = await import("react-dom/server");
  const { CSPProvider } = await import("@makeplane/propel/components/csp-provider");
  const { Tab, Tabs, TabsIndicator, TabsList } = await import("@makeplane/propel/components/tabs");
  const tabs = h(
    Tabs,
    { defaultValue: "a" },
    h(TabsList, null, h(Tab, { value: "a", label: "A" }), h(TabsIndicator, { renderBeforeHydration: true }))
  );
  const html = renderToString(h(CSPProvider, { nonce: "request-nonce" }, tabs));
  const scripts = [...html.matchAll(/<script\b[^>]*>/gi)].map(([tag]) => tag);
  assert.ok(scripts.length > 0, "the indicator renders its prehydration script on the server");
  for (const tag of scripts) assert.equal(attribute(tag, "nonce"), "request-nonce", tag);
});
