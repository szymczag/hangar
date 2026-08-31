// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

// Source-shape contract for project duplication.
//
// The API scopes its project-level permission check to the project id in the
// URL path, so a client that moved the source into the request body would be
// calling an endpoint with no project-level check at all. That is a security
// property of the *call shape*, which is why it is asserted here rather than
// left to the API tests alone.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));

function read(relativePath) {
  return readFileSync(path.join(repoRoot, relativePath), "utf8");
}

const service = read("apps/web/core/services/project/project.service.ts");
const store = read("apps/web/core/store/project/project.store.ts");
const modal = read("apps/web/core/components/project/duplicate-project-modal.tsx");

test("the source project is named in the path, never the request body", () => {
  const call = service.match(/duplicateProject\([\s\S]*?\n {2}}/);
  assert.ok(call, "duplicateProject is missing from the project service");

  assert.match(
    call[0],
    /this\.post\(\s*`\/api\/workspaces\/\$\{workspaceSlug\}\/projects\/\$\{projectId\}\/duplicate\/`/,
    "the source project id must be a path segment so the API can scope its permission check to it"
  );
  assert.doesNotMatch(call[0], /project_id|source_project/, "the source project must not be passed in the body");
});

test("duplication failures reach the form with the API's error code intact", () => {
  const call = service.match(/duplicateProject\([\s\S]*?\n {2}}/);

  // `createProject` rejects with `error.response`, and its callers read
  // `err.data.error`. Rejecting with `.response.data` here would silently break
  // the name/identifier collision handling in the modal.
  assert.match(
    call[0],
    /throw error\?\.response;/,
    "duplicateProject must reject with the response, matching createProject"
  );
  assert.match(modal, /\?\.data\?\.error/, "the modal must decode the API error code from the rejected response");
  assert.match(modal, /PROJECT_NAME_ALREADY_EXIST/);
  assert.match(modal, /PROJECT_IDENTIFIER_ALREADY_EXIST/);
});

test("a duplicated project lands in the store without a refetch", () => {
  assert.match(store, /duplicateProject: action,/, "the action must be observable");
  assert.match(
    store.match(/duplicateProject = async[\s\S]*?\n {2}};/)[0],
    /this\.processProjectAfterCreation\(/,
    "the response has the creation shape, so it must go through the same post-creation path"
  );
});

test("access-granting copy options stay off until they are asked for", () => {
  const seed = modal.match(/reset\(\{[\s\S]*?\}\);/);
  assert.ok(seed, "the modal must seed its form");

  for (const option of ["members", "cycles", "modules", "views"]) {
    assert.match(
      seed[0],
      new RegExp(`${option}: false`),
      `${option} must default to off; copying it silently grants access or carries someone else's work`
    );
  }
});

test("every entry point opens the one shared modal", () => {
  const entryPoints = [
    "apps/web/core/components/workspace/sidebar/projects-list-item.tsx",
    "apps/web/core/components/project/card.tsx",
    "apps/web/core/components/project/settings/control-section.tsx",
  ];

  for (const entryPoint of entryPoints) {
    const source = read(entryPoint);
    assert.match(
      source,
      /DuplicateProjectModal/,
      `${entryPoint} must reuse the shared duplicate modal rather than rolling its own`
    );
  }
});
