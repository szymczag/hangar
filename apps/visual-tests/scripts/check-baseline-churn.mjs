#!/usr/bin/env node
// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only
// See the LICENSE file for details.

/**
 * Refuse a pull request that quietly rewrites a pile of baselines.
 *
 * The failure this exists for is a real regression riding in with a batch of
 * legitimate updates: twenty images change, the reviewer sees "twenty files,
 * LGTM", and the one that mattered goes through. It is the second most likely
 * way this suite becomes worthless, after tolerance creep.
 *
 * Only *modifications* are counted. Adding new baselines is how coverage grows
 * and has no such failure mode -- a new image is reviewed on its own merits or
 * not at all, and either way nothing is being overwritten.
 *
 * Three is chosen so the one recurring legitimate rewrite passes without
 * ceremony: preparing a release moves the two build-identity baselines, because
 * that dialog photographs the release notes.
 *
 * The escape hatch is a line in the pull request body, because the point is to
 * make a large rewrite *stated* rather than to prevent it:
 *
 *     visual-baselines: hid the route progress bar, which four baselines had
 *
 * Usage: check-baseline-churn.mjs <base-ref> [pr-body-file]
 */

import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import process from "node:process";

const THRESHOLD = 3;
const BASELINES = "apps/visual-tests/baselines/";

const [baseRef, bodyFile] = process.argv.slice(2);
if (!baseRef) {
  console.error("usage: check-baseline-churn.mjs <base-ref> [pr-body-file]");
  process.exit(2);
}

// `--diff-filter=M` is the whole idea: added (A) baselines are new coverage.
const changed = execFileSync("git", ["diff", "--name-only", "--diff-filter=M", `${baseRef}...HEAD`, "--", BASELINES], {
  encoding: "utf8",
})
  .split("\n")
  .filter((line) => line.endsWith(".png"));

if (changed.length <= THRESHOLD) {
  console.log(`${changed.length} existing baseline(s) modified; at or under the threshold of ${THRESHOLD}.`);
  process.exit(0);
}

const body = bodyFile && existsSync(bodyFile) ? readFileSync(bodyFile, "utf8") : "";
const declared = /^\s*visual-baselines:\s*\S/im.test(body);

if (declared) {
  console.log(`${changed.length} existing baselines modified, and the pull request says why. Allowed.`);
  process.exit(0);
}

console.error(
  [
    `${changed.length} existing baselines are rewritten by this pull request, over the threshold of ${THRESHOLD}:`,
    "",
    ...changed.map((file) => `  ${file}`),
    "",
    "That is the shape a real regression hides in: a batch of legitimate updates",
    "with one wrong image among them, reviewed as a count rather than as pictures.",
    "",
    "If every one of them is intended, say so in the pull request body:",
    "",
    "  visual-baselines: <what changed, and why every one of these moved>",
    "",
    "Adding new baselines is not counted -- only rewriting existing ones.",
  ].join("\n")
);
process.exit(1);
