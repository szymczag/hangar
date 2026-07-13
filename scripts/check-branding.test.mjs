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

  assert.deepEqual([...new Set(violations.map(({ rule }) => rule))].sort(), [
    "plane-domain",
    "plane-email",
    "product-name",
    "upstream-repository",
  ]);
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
