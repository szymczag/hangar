// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

/**
 * Hangar's own features moved to Propel in phase 8: capacity (personal, team,
 * planner, report, calendar import), work item types and custom properties,
 * workshop sessions and the schedule row, the Todoist import wizard, the
 * copy progress strip and the build identity dialog. The maintenance bar is
 * not here: it sits above every page, so moving it moves every baseline, and it
 * gets its own pass.
 *
 * The move changed markup only. Each check below is a rule the new markup could
 * drop without a type error or a failing render:
 *
 * - every one of those files renders Propel and blocks controls, not
 *   `@plane/ui`, the in-repo `packages/propel`, Headless UI or lucide;
 * - the Todoist wizard links nowhere and never puts the preview token on
 *   screen: it only travels back to the server on import (S22/S25);
 * - the build identity dialog's documentation link stays behind
 *   `showExternalLinks`, while the source offer stays ungated (AGPL-3.0 s.13);
 * - work item types and the Workshops card stay admin-only to manage, and the
 *   calendar import stays admin-only behind its feature flag;
 * - the 1.4 filter rows the work item type filter used are gone, and the filter
 *   is a row of upstream's sub-work item filters menu.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relative) => readFileSync(path.join(root, relative), "utf8");

const sources = (relative) => {
  const absolute = path.join(root, relative);
  if (statSync(absolute).isFile()) return [relative];
  return readdirSync(absolute, { recursive: true })
    .filter((entry) => /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry))
    .map((entry) => path.join(relative, entry));
};

const FEATURES = [
  "app/(all)/[workspaceSlug]/(projects)/capacity",
  "ce/components/issue-types",
  "ce/components/issues",
  "ce/components/workspace/imports",
  "ce/components/project/copy-progress.tsx",
  "ce/components/license/modal/community-modal.tsx",
  "components/issues/issue-detail-widgets/workshop-sessions",
  "components/issues/issue-detail/workshop-schedule.tsx",
  "components/issues/issue-detail/issue-identifier.tsx",
].flatMap(sources);

const LEGACY = /from "(@plane\/ui|@plane\/propel(\/[^"]*)?|@headlessui\/react|lucide-react)"/;

test("the phase 8 file list is not empty", () => {
  assert.ok(FEATURES.length > 40, `expected the capacity, type, workshop and import sources, found ${FEATURES.length}`);
});

for (const file of FEATURES) {
  test(`${file} is built from Propel and blocks`, () => {
    assert.doesNotMatch(read(file), LEGACY);
  });
}

test("the Todoist wizard links nowhere and keeps the preview token off screen", () => {
  for (const file of [
    "ce/components/workspace/imports/todoist-import.tsx",
    "ce/components/workspace/imports/todoist-import-review.tsx",
  ]) {
    const source = read(file);
    assert.doesNotMatch(source, /https?:\/\//, `${file} must not carry an outbound address`);
    assert.doesNotMatch(source, /target="_blank"|window\.open/, `${file} must not open another page`);
  }
  const wizard = read("ce/components/workspace/imports/todoist-import.tsx");
  const uses = wizard.match(/preview_token/g) ?? [];
  assert.equal(uses.length, 1, "the preview token is read once, to send it back on import");
  assert.match(wizard, /importService\.startTodoist\([^)]*preview\.preview_token/);
  assert.doesNotMatch(read("ce/components/workspace/imports/todoist-import-review.tsx"), /preview_token/);
});

test("the build identity dialog gates documentation but not the source offer", () => {
  const modal = read("ce/components/license/modal/community-modal.tsx");
  assert.match(modal, /const linksAllowed = showExternalLinks\(config\)/);
  assert.match(modal, /\{linksAllowed && \(\s*<AnchorButton[^>]*href=\{documentationUrl\}/);
  assert.match(modal, /href=\{sourceUrl\}/);
  assert.doesNotMatch(modal, /linksAllowed && \(\s*<AnchorButton[^>]*href=\{sourceUrl\}/);
});

test("work item types and the Workshops card stay admin-only to manage", () => {
  const settings = read("ce/components/issue-types/settings-root.tsx");
  const card = read("ce/components/issue-types/workshops-card.tsx");
  assert.ok((settings.match(/\bisAdmin\b/g) ?? []).length >= 4, "the settings keep their isAdmin gates");
  assert.match(card, /is_google_calendar_capacity_enabled === true/);
  assert.ok((card.match(/\bisAdmin\b/g) ?? []).length >= 2, "the card keeps its isAdmin gate");
});

test("the calendar import stays admin-only behind its feature flag", () => {
  const page = read("app/(all)/[workspaceSlug]/(projects)/capacity/imports/page.tsx");
  assert.match(page, /featureEnabled && isAdmin \?/);
  assert.match(page, /if \(!isAdmin\) return <NotAuthorizedView/);
});

test("the work item type filter is a row of upstream's sub-work item filters menu", () => {
  const helpers = path.join(root, "components/issues/issue-layouts/filters/header/helpers");
  assert.deepEqual(readdirSync(helpers).toSorted(), ["dropdown.tsx", "index.ts"]);
  assert.match(read("ce/components/issues/filters/issue-types.tsx"), /<FilterSubmenu/);
  assert.match(
    read("components/issues/issue-detail-widgets/sub-issues/filters.tsx"),
    /isFilterEnabled\("issue_type"\) && \(\s*<FilterIssueTypes/
  );
});
