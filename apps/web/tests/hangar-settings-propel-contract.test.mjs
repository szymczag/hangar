// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * The Hangar-only settings pages moved to Propel in phase 3c: home defaults,
 * imports, workshop checklists, and the encrypted e-mail and receipt sections
 * of the account's security tab with the notice on the notifications tab.
 *
 * The move changed markup only. Each check below is a rule the new markup could
 * drop without a type error or a failing render:
 *
 * - the pages render Propel and blocks controls, not `@plane/ui` or the old
 *   in-repo Propel button, toast or loader;
 * - imports stay admin-only behind `is_todoist_imports_enabled`, and the
 *   history links only to Hangar's own report endpoint (S22/S25);
 * - deleting a workshop template or role still asks first, now in the blocks
 *   confirmation dialog instead of `window.confirm`;
 * - a key change asks for the current password unless the account has none
 *   (`is_password_autoset`, which a federated account has, S10), and removing
 *   or discarding a key still takes a second, confirming click;
 * - the notifications notice is still announced as an alert.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (relative) => readFileSync(new URL(`../${relative}`, import.meta.url), "utf8");

const SETTINGS = "app/(all)/[workspaceSlug]/(settings)/settings/(workspace)";
const PAGES = [
  `${SETTINGS}/home-defaults/page.tsx`,
  `${SETTINGS}/imports/page.tsx`,
  `${SETTINGS}/imports/header.tsx`,
  `${SETTINGS}/workshop-templates/page.tsx`,
  "ce/components/workspace/imports/todoist-import-history.tsx",
  "components/settings/profile/content/pages/email-security.tsx",
  "components/settings/profile/content/pages/email-receipts.tsx",
  "components/settings/profile/content/pages/notifications/email-security-notice.tsx",
];

for (const page of PAGES) {
  test(`${page} is built from Propel and blocks controls`, () => {
    const source = read(page);
    assert.doesNotMatch(source, /from "@plane\/ui"/, "no @plane/ui controls left");
    assert.doesNotMatch(source, /from "@plane\/propel\/(button|toast)"/, "no in-repo Propel button or toast left");
    assert.doesNotMatch(source, /from "lucide-react"/, "icons come from @makeplane/propel/icons");
  });
}

test("imports stay admin-only and link nowhere outside Hangar", () => {
  const page = read(`${SETTINGS}/imports/page.tsx`);
  assert.match(page, /allowPermissions\(\[EUserPermissions\.ADMIN\], EUserPermissionsLevel\.WORKSPACE\)/);
  assert.match(page, /!config\.is_todoist_imports_enabled \|\| \(workspaceUserInfo && !isAdmin\)/);

  const history = read("ce/components/workspace/imports/todoist-import-history.tsx");
  assert.match(history, /href=\{importService\.reportUrl\(workspaceSlug, job\.id\)\}/);
  assert.doesNotMatch(history, /https?:\/\//, "no outbound address in the history");
  assert.doesNotMatch(history, /\bexternal\b/, "no link opens outside Hangar");
});

test("workshop deletions still ask first, in the confirmation dialog", () => {
  const page = read(`${SETTINGS}/workshop-templates/page.tsx`);
  assert.doesNotMatch(page, /window\.confirm/);
  assert.match(page, /<ConfirmDialog/);
  assert.match(page, /onClick=\{\(\) => setPendingDeletion\(\{ kind: "role", role \}\)\}/);
  assert.match(page, /onClick=\{\(\) => setPendingDeletion\(\{ kind: "template", template \}\)\}/);
  assert.match(page, /config && !featureEnabled\) return <NotAuthorizedView/, "the feature gate is unchanged");
});

test("key changes ask for the current password and confirm a removal", () => {
  const source = read("components/settings/profile/content/pages/email-security.tsx");
  assert.match(source, /const passwordRequired = !currentUser\?\.is_password_autoset;/);
  // Upload, replace, remove and discard are all held back without it.
  assert.equal((source.match(/passwordRequired && !password/g) ?? []).length, 4);
  assert.match(source, /confirmRemoval === data\.active_key!\.id\s*\?\s*void remove\(data\.active_key!\.id\)/);
  assert.match(source, /confirmRemoval === data\.pending_key!\.id\s*\?\s*void remove\(data\.pending_key!\.id\)/);
  assert.match(source, /autoComplete="current-password"/);
});

test("the notifications notice is still announced as an alert", () => {
  const source = read("components/settings/profile/content/pages/notifications/email-security-notice.tsx");
  // The danger banner carries role="alert".
  assert.match(source, /<Banner\s+variant="danger"/);
});
