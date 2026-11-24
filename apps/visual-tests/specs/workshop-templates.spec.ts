/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Page } from "@playwright/test";
import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * Workspace settings → Workshop checklists, a Hangar-only page.
 *
 * The seed has no workshop roles or checklist templates, and creating them from
 * the browser is a write the guard refuses. The two list responses are
 * therefore answered here, with one role and one default template whose three
 * subtasks use three of the four assignee modes. Everything else -- the
 * workspace members the role rows list, the feature gate
 * (`ENABLE_GOOGLE_CALENDAR_CAPACITY`, set by the stack) -- is the seeded round
 * trip.
 *
 * Opening the template is a click on its chip, which only selects it in the
 * page's own state; nothing is saved.
 */
const ROLE = { id: "20000000-0000-4000-8000-000000000001", name: "Streaming", member_ids: [] as string[] };

const TEMPLATE = {
  id: "20000000-0000-4000-8000-000000000002",
  name: "Standard workshop",
  is_default: true,
  items: [
    {
      id: "20000000-0000-4000-8000-000000000003",
      position: 0,
      title: "Book the room",
      description: "",
      assignee_id: null,
      assignee_mode: "unassigned",
      role_id: null,
      offset_days: -14,
    },
    {
      id: "20000000-0000-4000-8000-000000000004",
      position: 1,
      title: "Send the joining instructions",
      description: "",
      assignee_id: null,
      assignee_mode: "workshop_trainer",
      role_id: null,
      offset_days: -1,
    },
    {
      id: "20000000-0000-4000-8000-000000000005",
      position: 2,
      title: "Publish the recording",
      description: "",
      assignee_id: null,
      assignee_mode: "role",
      role_id: ROLE.id,
      offset_days: 2,
    },
  ],
};

async function answerLists(page: Page): Promise<void> {
  await page.route(
    (url) => url.pathname.endsWith("/capacity/workshop-roles/"),
    (route) => (route.request().method() === "GET" ? route.fulfill({ json: { results: [ROLE] } }) : route.fallback())
  );
  await page.route(
    (url) => url.pathname.endsWith("/capacity/checklist-templates/"),
    (route) =>
      route.request().method() === "GET" ? route.fulfill({ json: { results: [TEMPLATE] } }) : route.fallback()
  );
}

test("workspace settings: workshop roles", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();
  await answerLists(page);

  await page.goto(`/${seed.workspace.slug}/settings/workshop-templates`);

  // The role's name, so the shot cannot be of the list before it arrived.
  const role = main.getByText(ROLE.name, { exact: true }).first();
  await expect(role).toBeVisible();
  await expect(main.getByText(/not authorized/i)).toHaveCount(0);

  await capture(page, "workspace-workshop-roles", {
    ready: role,
    target: main.getByRole("region", { name: "Workshop roles" }),
  });
});

test("workspace settings: a workshop checklist template", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();
  await answerLists(page);

  await page.goto(`/${seed.workspace.slug}/settings/workshop-templates`);

  const templates = main.getByRole("region", { name: "Checklist templates" });
  await templates
    .getByRole("button", { name: new RegExp(TEMPLATE.name) })
    .first()
    .click();

  // The last subtask's title is filled in only once the editor took the template.
  const lastItem = templates.getByRole("textbox", { name: "Subtask" }).nth(2);
  await expect(lastItem).toHaveValue(TEMPLATE.items[2].title);

  await capture(page, "workspace-workshop-template", { ready: lastItem, target: templates });
});
