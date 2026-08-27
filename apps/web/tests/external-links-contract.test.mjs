// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Links to hosts this instance does not run must be switchable off.
 *
 * Hangar is deployed inside organisations. A link to a code-hosting site is a
 * link out of the building for somebody who did not ask to leave it, and it
 * tells the far end who is looking and from where. `INSTANCE_SHOW_EXTERNAL_LINKS`
 * is off by default, so every such link has to be behind it.
 *
 * Two things are exempt, and the exemptions are named here rather than left to
 * whoever reads the file next:
 *
 *   - the AGPL source offer, which section 13 requires of anyone running a
 *     modified version over a network. An operator who wants that inside the
 *     building points HANGAR_SOURCE_URL at their own mirror.
 *   - the startup-failure page, which renders precisely when the instance did
 *     not come up and no configuration can be read, and which an operator sees
 *     rather than a user.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const WEB = path.dirname(path.dirname(fileURLToPath(new URL("../tests/x", import.meta.url))));

const EXEMPT = new Set([
  // Renders when the instance failed to start; there is no config to consult.
  "maintenance-message.tsx",
  // The error boundary, for the same reason.
  "prod.tsx",
]);

function* sources(directory) {
  for (const entry of readdirSync(directory)) {
    if (["node_modules", "build", "dist", ".turbo", "tests"].includes(entry)) continue;
    const full = path.join(directory, entry);
    if (statSync(full).isDirectory()) yield* sources(full);
    else if (/\.tsx$/.test(entry)) yield full;
  }
}

const allSources = () => [
  ...sources(path.join(WEB, "core")),
  ...sources(path.join(WEB, "app")),
  ...sources(path.join(WEB, "ce")),
];

test("this test can see the components it is meant to check", () => {
  assert.ok(allSources().length > 100, "expected the web components; looking at the wrong place");
});

test("every outbound link is either gated, the licence offer, or exempt", () => {
  const offenders = [];
  for (const file of allSources()) {
    const name = path.basename(file);
    if (EXEMPT.has(name)) continue;
    const source = readFileSync(file, "utf8");
    if (!/href=["{]?["']?https?:\/\//.test(source)) continue;
    // The licence offer reads its address from configuration, so an operator can
    // point it at their own mirror; it is allowed to render unconditionally.
    const isLicenceOffer = source.includes("sourceUrl") || source.includes("SOURCE_CODE_URL");
    if (isLicenceOffer && !/href="https?:\/\//.test(source)) continue;
    if (!source.includes("showExternalLinks")) offenders.push(path.relative(WEB, file));
  }

  assert.deepEqual(
    offenders,
    [],
    "these send whoever clicks them to somebody else's server with no way for an " +
      `operator to turn that off: ${offenders.join(", ")}`
  );
});
