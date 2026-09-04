#!/usr/bin/env node
// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only
// See the LICENSE file for details.

/**
 * Lint the visual suite for the things that quietly turn it into noise.
 *
 * None of these are style preferences. Each one is a specific way this kind of
 * suite dies, and each is far easier to prevent than to notice a year later:
 * the tolerance that got bumped during one flake and never came back down, the
 * readiness wait that was replaced by a sleep, the screenshot of a page that had
 * not finished rendering. A reviewer cannot reliably catch these in a diff --
 * they all look like small reasonable edits.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const SUITE = path.resolve(import.meta.dirname, "..");
const CAPTURE = path.join("src", "capture.ts");
const CONFIG = "playwright.config.ts";

/** @type {{ pattern: RegExp, message: string, appliesTo?: (rel: string) => boolean }[]} */
const RULES = [
  {
    pattern: /\bnetworkidle\b/,
    message:
      "`networkidle` never fires here -- the maintenance bar polls every 60s and the copy strip every 3s. Wait on rendered content instead.",
  },
  {
    pattern: /waitForTimeout\s*\(/,
    message:
      "A sleep is not a readiness check: it is slower than the page on a fast run and shorter than it on a slow one. Wait on a locator.",
  },
  {
    pattern: /\b(maxDiffPixels|maxDiffPixelRatio|threshold)\s*:/,
    message:
      "Tolerance is defined once, in playwright.config.ts, and is zero. An inline tolerance is how a real regression gets waved through.",
    // The config is where that single definition lives; anywhere else it is an override.
    appliesTo: (rel) => rel !== CONFIG,
  },
  {
    pattern: /fullPage\s*:\s*true/,
    message:
      "`fullPage` stitches a scrolling screenshot and captures lazy content mid-load. Capture an element, or the viewport for a named layout story.",
  },
  {
    pattern: /\btimeout\s*:/,
    message:
      "Timeouts are set once, in playwright.config.ts. A local override is why the suite waited 30s in some places and 60s in others, and the shorter number silently decided which stories failed under load.",
    appliesTo: (rel) => rel !== CONFIG,
  },
  {
    // capture() is where readiness, fonts and the settled checks live; a raw
    // assertion skips all of it and looks identical in review.
    pattern: /toHaveScreenshot\s*\(/,
    message: "Take screenshots through `capture()` from src/capture.ts, which enforces a readiness locator.",
    appliesTo: (rel) => rel !== CAPTURE,
  },
];

/** Every .ts file in the suite, excluding build output and baselines. */
function sourceFiles(dir = SUITE, found = []) {
  for (const entry of readdirSync(dir)) {
    if (["node_modules", "baselines", "test-results", "playwright-report"].includes(entry)) continue;
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) sourceFiles(full, found);
    else if (entry.endsWith(".ts")) found.push(full);
  }
  return found;
}

const violations = [];

for (const file of sourceFiles()) {
  const rel = path.relative(SUITE, file);
  const lines = readFileSync(file, "utf8").split("\n");

  lines.forEach((line, index) => {
    // Rules describe what the suite may *do*, so a comment explaining why a
    // thing is banned must not itself trip the rule that bans it.
    const code = line.replace(/\/\/.*$/, "").replace(/^\s*\*.*$/, "");
    for (const rule of RULES) {
      if (rule.appliesTo && !rule.appliesTo(rel)) continue;
      if (rule.pattern.test(code)) {
        violations.push(`${rel}:${index + 1}\n    ${line.trim()}\n    ${rule.message}`);
      }
    }
  });
}

if (violations.length > 0) {
  console.error(`Visual suite invariants violated (${violations.length}):\n`);
  for (const v of violations) console.error(`  ${v}\n`);
  process.exit(1);
}

console.log("Visual suite invariants hold.");
