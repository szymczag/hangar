// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * No page may load executable code from a host this instance does not control.
 *
 * Hangar is deployed inside organisations. A script tag pointing anywhere else
 * hands every signed-in person's address, and whatever the script chooses to
 * collect, to a third party — and it does so before anyone can object, because
 * it runs on load.
 *
 * Upstream shipped Microsoft Clarity, a session recorder, behind an environment
 * flag. Off by default is not the same as absent: the code was there, one
 * configuration change away, in an application whose whole point is that its
 * contents stay inside the building.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const APP = path.dirname(fileURLToPath(new URL("../app/root.tsx", import.meta.url)));
const CORE = path.dirname(fileURLToPath(new URL("../core/lib/store-context.tsx", import.meta.url)));

// Hosts a page may fetch executable code or embed content from. Empty on
// purpose: everything the application needs, it serves itself.
const ALLOWED_HOSTS = [];

function* sources(directory) {
  for (const entry of readdirSync(directory)) {
    if (entry === "node_modules" || entry === "build" || entry === "dist") continue;
    const full = path.join(directory, entry);
    if (statSync(full).isDirectory()) yield* sources(full);
    else if (/\.(tsx?|jsx?|mjs)$/.test(entry) && !entry.includes(".test.")) yield full;
  }
}

function allSources() {
  return [...sources(APP), ...sources(path.dirname(CORE))];
}

test("this test can see the files it is meant to check", () => {
  assert.ok(allSources().length > 20, "expected the web sources; looking at the wrong place");
});

test("nothing loads a script from another host", () => {
  const offenders = [];
  for (const file of allSources()) {
    const source = readFileSync(file, "utf8");
    for (const match of source.matchAll(/\.src\s*=\s*["'`]https?:\/\/([^"'`/]+)/g)) {
      if (!ALLOWED_HOSTS.includes(match[1])) offenders.push(`${path.basename(file)}: ${match[1]}`);
    }
    for (const match of source.matchAll(/<script[^>]+src=["'{]https?:\/\/([^"'`/]+)/gi)) {
      if (!ALLOWED_HOSTS.includes(match[1])) offenders.push(`${path.basename(file)}: ${match[1]}`);
    }
  }

  assert.deepEqual(
    offenders,
    [],
    `these run third-party code in every signed-in person's browser: ${offenders.join(", ")}`
  );
});

test("the session recorder is gone rather than switched off", () => {
  for (const file of allSources()) {
    const source = readFileSync(file, "utf8");
    assert.doesNotMatch(source, /clarity\.ms/i, `${path.basename(file)} still reaches Microsoft Clarity`);
    assert.doesNotMatch(
      source,
      /VITE_(ENABLE_)?SESSION_RECORDER/,
      `${path.basename(file)} still carries the recorder switch, so the code is one setting away`
    );
  }
});
