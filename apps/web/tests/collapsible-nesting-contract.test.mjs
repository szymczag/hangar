// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * A Collapsible already provides its panel. Nesting another one breaks it.
 *
 * `Collapsible` renders `<Disclosure><Transition show={isOpen}><Disclosure.Panel
 * static>{children}</Disclosure.Panel></Transition></Disclosure>`. A second,
 * non-static `Disclosure.Panel` placed among those children lands inside that
 * same Disclosure context and follows headlessui's own open state, which starts
 * closed — so the section animates open and shows nothing, which reads as
 * expanding and immediately collapsing again.
 *
 * The pending-invites list did this and the section was unusable.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOTS = ["../core", "../app"].map((relative) => path.dirname(fileURLToPath(new URL(relative, import.meta.url))));

function* sources(directory) {
  for (const entry of readdirSync(directory)) {
    const full = path.join(directory, entry);
    if (entry === "node_modules" || entry === "build") continue;
    if (statSync(full).isDirectory()) yield* sources(full);
    else if (entry.endsWith(".tsx")) yield full;
  }
}

function allSources() {
  const files = [];
  for (const root of ROOTS) {
    for (const file of sources(path.join(root, path.basename(root) === "web" ? "" : ""))) files.push(file);
  }
  return files;
}

test("this test can see the components it is meant to check", () => {
  assert.ok(allSources().length > 100, "expected the web components; looking at the wrong place");
});

test("no component puts a Disclosure.Panel inside a Collapsible", () => {
  const offenders = [];
  for (const file of allSources()) {
    const source = readFileSync(file, "utf8");
    if (source.includes("<Collapsible") && source.includes("<Disclosure.Panel")) {
      offenders.push(path.relative(process.cwd(), file));
    }
  }

  assert.deepEqual(
    offenders,
    [],
    "Collapsible supplies its own panel; a nested one follows headlessui's open " +
      `state instead and renders nothing: ${offenders.join(", ")}`
  );
});
