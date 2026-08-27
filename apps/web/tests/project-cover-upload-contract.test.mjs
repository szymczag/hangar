// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * A project's cover is stored against the project, so it cannot be uploaded
 * before the project exists.
 *
 * An asset upload names the record it belongs to. During creation there is no
 * project id yet, and the empty string that was sent instead is refused by the
 * API — see plane/tests/contract/app/test_asset_entity_identifier.py. Because
 * new projects are given a random bundled cover by default, that refusal was
 * reached by anyone who created a project without changing the image, and it
 * aborted the creation entirely rather than costing only the cover.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../core/components/projects/create/root.tsx", import.meta.url), "utf8");
const defaults = readFileSync(new URL("../core/components/projects/create/utils.ts", import.meta.url), "utf8");

test("a new project is still given a cover by default, which is what makes this reachable", () => {
  assert.match(
    defaults,
    /cover_image_url: getRandomCoverImage\(\)/,
    "if the default cover is gone this test guards a path nobody takes; check whether it still earns its place"
  );
});

test("the upload never names an empty record", () => {
  assert.doesNotMatch(
    source,
    /entityIdentifier: ""/,
    "the API refuses an empty entity_identifier, so this cannot upload anything"
  );
  assert.match(source, /entityIdentifier: projectId/, "the upload should name the project it belongs to");
});

test("the upload happens after the project has been created", () => {
  const createdAt = source.indexOf("createProject(workspaceSlug.toString(), formData)");
  const uploadAt = source.indexOf("uploadCoverImage(");
  const attachAt = source.indexOf("attachBundledCover(res.id");

  assert.ok(createdAt !== -1, "expected the creation call; this test is looking at the wrong shape");
  assert.ok(attachAt > createdAt, "the cover must be attached from inside the post-creation block");
  assert.ok(
    uploadAt === -1 || source.slice(uploadAt).includes("entityIdentifier: projectId"),
    "the only upload here should be the one that names the project"
  );
});

test("a cover that cannot be stored does not discard the project", () => {
  const attachAt = source.indexOf("attachBundledCover(res.id");
  const guarded = source.slice(Math.max(0, attachAt - 400), attachAt + 600);

  assert.match(guarded, /try \{/, "the attach must be attempted, not assumed");
  assert.match(guarded, /catch/, "a failure has to be caught once the project already exists");
  assert.doesNotMatch(guarded, /return Promise\.reject/, "rejecting here would throw away the created project");
});
