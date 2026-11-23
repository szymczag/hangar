// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Deleting or leaving a project asks for the project's name first.
 *
 * Both moved to the blocks `TypeToConfirmDialog` with the rest of the project
 * screens. The dialog keeps its confirm button disabled until every field
 * matches its `expectedValue`, so the guard is the field list: drop it, or let
 * it expect something the person does not have to type, and one stray click
 * removes a project and everything in it.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (relative) => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8");

for (const [file, action] of [
  ["components/project/delete-project-modal.tsx", "deleteProject"],
  ["components/project/leave-project-modal.tsx", "leaveProject"],
]) {
  test(`${file} confirms with the project's name before ${action}`, () => {
    const source = read(file);
    assert.match(source, /<TypeToConfirmDialog/, "the confirmation dialog must stay");
    assert.match(source, /expectedValue: project\?\.name \?\? ""/, "the field must expect the project's own name");
    assert.match(source, /onConfirm=\{onSubmit\}/, "the action must run only from the confirmed dialog");
    assert.ok(source.includes(`${action}(`), `the dialog must be what calls ${action}`);
  });
}

test("the dialog keeps its confirm button disabled until every field matches", () => {
  const dialog = readFileSync(
    new URL("../../../packages/blocks/src/dialog/type-to-confirm-dialog.tsx", import.meta.url),
    "utf8"
  );
  assert.match(
    dialog,
    /fields\.every\(\s*\(field\) => field\.expectedValue\.length > 0 && \(values\[field\.name\] \?\? ""\)\.trim\(\) === field\.expectedValue/,
    "every field must be typed out in full, and an empty expected value must never count as a match"
  );
  assert.match(dialog, /disabled=\{!canConfirm\}/, "the confirm button must stay disabled until then");
});
