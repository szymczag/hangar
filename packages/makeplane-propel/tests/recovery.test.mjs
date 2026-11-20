// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// The recovered files are upstream's code and stay byte for byte as the
// recovery wrote them. Hangar changes, if ever needed, go into separate files,
// never into these. This test fails on any edit, addition or removal under
// src/ that RECOVERY.json does not record.

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const manifest = JSON.parse(readFileSync(join(root, "RECOVERY.json"), "utf8"));

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [relative(root, path).split("\\").join("/")];
  });
}

test("manifest describes the pinned upstream release", () => {
  assert.equal(manifest.package, "@makeplane/propel");
  assert.equal(manifest.version, JSON.parse(readFileSync(join(root, "package.json"), "utf8")).version);
  assert.match(manifest.integrity, /^sha512-[A-Za-z0-9+/]+={0,2}$/);
});

test("every recovered file matches its recorded SHA-256", () => {
  const mismatched = manifest.files.filter(
    (file) =>
      createHash("sha256")
        .update(readFileSync(join(root, file.path)))
        .digest("hex") !== file.sha256
  );
  assert.deepEqual(
    mismatched.map((file) => file.path),
    [],
    "recovered files were edited; re-run scripts/propel/recover.mjs instead"
  );
});

test("src/ holds exactly the recovered files", () => {
  const recorded = new Set(manifest.files.map((file) => file.path));
  const present = walk(join(root, "src"));
  assert.deepEqual(
    present.filter((path) => !recorded.has(path)),
    [],
    "files under src/ that the recovery did not produce"
  );
  assert.deepEqual(
    [...recorded].filter((path) => path.startsWith("src/") && !present.includes(path)),
    [],
    "recovered files missing from src/"
  );
});

test("every file has a known origin and the counts agree", () => {
  const origins = new Set(["sourcemap", "barrel", "dts", "inlined-constant", "copied"]);
  for (const file of manifest.files) assert.ok(origins.has(file.origin), `${file.path}: ${file.origin}`);
  const counts = Object.fromEntries([...origins].map((origin) => [origin, 0]));
  for (const file of manifest.files) counts[file.origin] += 1;
  assert.deepEqual(counts, manifest.counts);
});
