// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import test from "node:test";

import { findViolationsInText } from "./check-branding.mjs";

test("rejects public Plane product and support references", () => {
  const violations = findViolationsInText(
    "apps/web/example.tsx",
    'const message = "Contact Plane at help@plane.so or github.com/makeplane/plane";'
  );

  assert.deepEqual([...new Set(violations.map(({ rule }) => rule))].toSorted(), [
    "plane-domain",
    "plane-email",
    "product-name",
    "upstream-repository",
  ]);
});

test("rejects the product named in lower case in sign-in copy", () => {
  for (const copy of [
    "Allow members to log in or sign up to plane with their GitLab accounts.",
    "Allow members to login or sign up to plane with their Gitea accounts.",
    "Welcome to plane",
  ]) {
    const violations = findViolationsInText("apps/admin/example.tsx", copy);
    assert.deepEqual(
      violations.map(({ rule }) => rule),
      ["product-name-lowercase"],
      copy
    );
  }
});

test("does not flag lower-case plane identifiers", () => {
  assert.deepEqual(
    findViolationsInText("apps/web/example.tsx", 'import { cn } from "@plane/utils"; const plane = usePlane();'),
    []
  );
});

test("accepts Hangar product copy", () => {
  assert.deepEqual(findViolationsInText("apps/web/example.tsx", 'const message = "Open a Hangar GitHub issue";'), []);
});

test("allows a narrowly documented compatibility reference", () => {
  const allowlist = [
    {
      pathPattern: "^apps/web/legacy\\.tsx$",
      rules: ["plane-domain", "plane-email"],
      rationale: "Test fixture",
    },
  ];

  assert.deepEqual(findViolationsInText("apps/web/legacy.tsx", 'const bot = "intake@plane.so";', allowlist), []);
});
