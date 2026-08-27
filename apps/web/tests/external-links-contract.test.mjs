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
 * One thing is exempt: the AGPL source offer, which section 13 requires of
 * anyone running a modified version over a network. An operator who wants that
 * inside the building points HANGAR_SOURCE_URL at their own mirror.
 *
 * The failure pages were exempt too, on the grounds that they render when no
 * configuration can be read. That was true and the wrong conclusion — they are
 * what a company's staff see the moment their tools stop working. They now read
 * what was remembered while the instance could still be asked.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const WEB = path.dirname(path.dirname(fileURLToPath(new URL("../tests/x", import.meta.url))));

// Nothing is exempt. The failure pages were, on the grounds that they render
// when no configuration can be read — which is true, and was the wrong
// conclusion: they are what a company's staff see the moment their tools stop
// working, and they were inviting them to file a public bug report. They now
// read what was remembered from the last successful start.
const EXEMPT = new Set([]);

// Hosts that are not destinations: XML namespaces, and the placeholders used in
// examples and stories. Compared as whole host names — matching a substring
// would let https://evil.example/www.w3.org through, which is the same mistake
// this file exists to catch elsewhere.
const IGNORED_HOSTS = new Set(["www.w3.org", "example.com", "dummy.com", "localhost"]);

const hostOf = (address) => {
  try {
    return new URL(address).hostname.toLowerCase();
  } catch {
    return "";
  }
};

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

test("every outbound link is either gated or the licence offer", () => {
  const offenders = [];
  for (const file of allSources()) {
    if (EXEMPT.has(path.basename(file))) continue;
    const source = readFileSync(file, "utf8");

    // Any absolute address written into the file, not only one sitting directly
    // in an href. The startup-failure page kept its link in a lookup table and
    // rendered it as href={link.value}, which an href-shaped check walked past —
    // and that page was the one that mattered most.
    const addresses = [];
    for (const line of source.split("\n")) {
      // Metadata, not a destination: og:url and friends are read by crawlers and
      // never presented to anyone as something to click.
      if (/property:|content:|name="og:/.test(line)) continue;
      for (const match of line.matchAll(/["'`](https?:\/\/[^"'`\s]+)["'`]/g)) {
        // Built at runtime from what somebody typed or from an integration's own
        // configuration — a link the application carries, not one it ships.
        if (match[1].includes("${")) continue;
        addresses.push(match[1]);
      }
    }
    const outbound = addresses.filter((address) => {
      const host = hostOf(address);
      return host !== "" && !IGNORED_HOSTS.has(host);
    });
    if (outbound.length === 0) continue;

    // The licence offer reads its address from configuration, so an operator can
    // point it at their own mirror. It is allowed to render unconditionally.
    const everyAddressIsTheRepository = outbound.every((address) => {
      const host = hostOf(address);
      return host === "github.com" || host.endsWith(".github.com");
    });
    if (/SOURCE_CODE_URL|sourceUrl/.test(source) && everyAddressIsTheRepository) {
      if (!/ISSUE_TRACKER_URL|\/issues/.test(source)) continue;
    }

    if (!source.includes("showExternalLinks")) offenders.push(`${path.relative(WEB, file)}: ${outbound[0]}`);
  }

  assert.deepEqual(
    offenders,
    [],
    "these send whoever clicks them to somebody else's server with no way for an " +
      `operator to turn that off: ${offenders.join(", ")}`
  );
});
