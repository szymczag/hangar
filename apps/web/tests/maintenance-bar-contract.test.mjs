// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

const root = read("app/root.tsx");
const bar = read("ce/components/instance/maintenance-bar.tsx");
const helper = read("helpers/maintenance-notice.ts");
const service = read("../../packages/services/src/instance/instance-maintenance.service.ts");

test("the app's own height survives the bar being given a slot", () => {
  // `<main>` sits in a `flex-col h-screen`. Left as `h-full` it would push the
  // app's bottom edge past the viewport the moment it has a sibling, and the
  // parent's `overflow-hidden` would clip it. This is the assertion that
  // catches an upstream merge quietly restoring `h-full`.
  const main = /<main className="([^"]+)"/.exec(root)?.[1];

  assert.ok(main, "root.tsx must still render a <main> with a className");
  assert.match(main, /\bflex-1\b/);
  assert.match(main, /\bmin-h-0\b/, "nested scroll containers refuse to shrink below content without it");
  assert.doesNotMatch(main, /\bh-full\b/);
});

test("the bar sits above main, where an error view cannot hide it", () => {
  // Inside InstanceWrapper it would vanish on an API error or an unfinished
  // setup -- exactly when an operator needs to say something.
  const barIndex = root.indexOf("<MaintenanceBar />");
  const mainIndex = root.indexOf("<main className");

  assert.ok(barIndex > 0, "root.tsx must render the bar");
  assert.ok(barIndex < mainIndex, "the bar must precede <main>");
});

test("the notice is polled rather than read from the cached instance payload", () => {
  // `/api/instances/` is cached two hours server-side and fetched once per tab
  // with revalidateOnFocus off; a notice riding it would reach nobody already
  // working.
  assert.match(bar, /refreshInterval:\s*60_000/);
  assert.match(bar, /revalidateOnFocus:\s*true/);
  assert.match(bar, /revalidateOnReconnect:\s*true/);
});

test("the public read stays off the admin cookie's path prefix", () => {
  // The session middleware switches to the instance-admin cookie on any path
  // containing "instances", which would make every signed-in reader look
  // anonymous and silently reduce them to the sign-in gate.
  assert.match(service, /this\.get\("\/api\/maintenance\/"\)/);
  assert.doesNotMatch(
    service,
    /retrieve\(\)[\s\S]{0,200}\/api\/instances\/maintenance/,
    "the anonymous read must not sit under /api/instances/"
  );
});

test("an unreachable API does not erase the notice it last gave us", () => {
  // The outage worth announcing is the one that takes the API down with it.
  assert.match(bar, /recalledMaintenanceNotice\(\)/);
  assert.match(bar, /if \(data !== undefined\) rememberMaintenanceNotice/);
});

test("every storage access tolerates a private window", () => {
  const accesses = helper.match(/window\.localStorage\./g) ?? [];
  const guards = helper.match(/\btry\s*\{/g) ?? [];

  assert.ok(accesses.length >= 4, "expected the helper to read and write storage");
  assert.ok(guards.length >= 4, "every localStorage access must sit inside try/catch");
});

test("dismissal keys off the wording, not a counter", () => {
  // Toggling the same notice off and on must not re-nag someone who read it;
  // editing what it says must bring it back for everyone.
  assert.match(bar, /notice\.fingerprint === dismissed/);
});

test("the bar renders nothing rather than something empty", () => {
  assert.match(bar, /if \(!notice \|\| notice\.fingerprint === dismissed\) return null;/);
});
