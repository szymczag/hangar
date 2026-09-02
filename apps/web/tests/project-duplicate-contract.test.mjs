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
  // The endpoint answers in two shapes and the modal has to read both: the copy
  // service raises `{ error: CODE }`, while a serializer rejection is DRF's
  // field map, `{ name: [CODE] }`. Decoding only the first sent every
  // validation failure to the generic toast with nothing said about the field.
  assert.match(modal, /body\.error/, "the modal must decode the service's { error: CODE } shape");
  assert.match(modal, /Array\.isArray\(value\)/, "the modal must decode DRF's { field: [CODE] } shape");
  assert.match(modal, /PROJECT_NAME_ALREADY_EXIST/);
  assert.match(modal, /PROJECT_IDENTIFIER_ALREADY_EXIST/);
  assert.match(modal, /PROJECT_NAME_CANNOT_CONTAIN_SPECIAL_CHARACTERS/);
});

test("the name the modal prefills is one the endpoint accepts", () => {
  // These two drifted apart once already: the modal seeds "<source> (Copy)"
  // while the endpoint applied the identifier's character rule to the name, so
  // the modal's own default value was rejected and duplication could never
  // succeed from the interface. Pin them together.
  const seeded = /name: `\$\{project\.name\} \(Copy\)`/.test(modal);
  assert.ok(seeded, "the modal seeds the name with a (Copy) suffix");

  const serializer = readFileSync(new URL("../../api/plane/ext/serializers/project_copy.py", import.meta.url), "utf8");
  const validateName = serializer.match(/def validate_name[\s\S]*?(?=\n    def )/)[0];

  assert.doesNotMatch(
    validateName,
    /FORBIDDEN_IDENTIFIER_CHARS_PATTERN/,
    "the display name must not be held to the identifier's character rule"
  );
  assert.match(validateName, /validate_single_line_text/);
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

test("the create modal starts from a source instead of creating an empty project", () => {
  // `templateId` was declared and threaded through this path upstream but never
  // read, so the picker silently did nothing. Guard against it going dead again.
  const form = read("apps/web/core/components/projects/create/root.tsx");
  const createModal = read("apps/web/core/components/project/create-project-modal.tsx");
  const header = read("apps/web/core/components/project/create/header.tsx");

  assert.match(form, /templateId[,\s}]/, "the create form must destructure templateId, not just declare it");
  assert.match(
    form,
    /templateId\s*\n?\s*\?\s*duplicateProject\(/,
    "with a source chosen the form must duplicate, not create an empty project"
  );
  assert.match(
    form,
    /isBundledCover && !templateId/,
    "the server owns the cover on the duplicate path; the client must not also attach one"
  );
  assert.match(header, /handleTemplateSelect &&/, "the header must render the picker entry point");
  assert.match(createModal, /SOURCE_SELECTION/, "the modal needs a step for choosing the source");
});

test("only projects the user administers can be copied from", () => {
  // The API requires ADMIN on the source, because duplication re-links shared
  // work item types. The picker must not offer projects it would refuse.
  const picker = read("apps/web/core/components/project/create/source-picker.tsx");
  assert.match(picker, /member_role === EUserPermissions\.ADMIN/);
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
