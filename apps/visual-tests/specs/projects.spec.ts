/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Page } from "@playwright/test";
import { capture, settled } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The projects list, the create modal and the project settings pages.
 *
 * These moved to Propel in phase 3a (FORK.md ledger). None of them had a
 * baseline before, so each page that the move restyles gets one: the list of
 * project cards, the create modal, and the settings pages an admin works
 * through (general, members, a feature page, states, labels, estimates,
 * automations).
 *
 * Every story is read-only: the settings forms are opened and photographed,
 * never submitted, so the write guard stays quiet.
 */

/** The admin's view of one project settings page, waited on until `ready` shows. */
async function projectSettings(page: Page, path: string, ready: string): Promise<void> {
  const seed = fixtures();
  const suffix = path ? `/${path}` : "";
  await page.goto(`/${seed.workspace.slug}/settings/projects/${seed.project.id}${suffix}`);
  const main = page.getByRole("main").last();
  await expect(main.getByText(ready, { exact: true }).first()).toBeVisible();
  await capture(page, `project-settings-${path.replace(/\//g, "-") || "general"}`, {
    ready: main.getByText(ready, { exact: true }).first(),
    target: main,
  });
}

test("the projects list", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/projects`);
  const card = main.getByText("Visual Regression", { exact: true }).first();

  await capture(page, "projects-list", { ready: card, target: main });
});

test("the create project modal", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();

  // A new project is given a random bundled cover; pin the pick so the
  // photograph does not change from run to run.
  await page.addInitScript(() => {
    Math.random = () => 0;
  });
  await page.goto(`/${seed.workspace.slug}/projects`);
  await expect(page.getByRole("main").last().getByText("Visual Regression", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Add Project" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Create project" });
  await settled(dialog);
  const name = dialog.getByPlaceholder("Project name");

  await capture(page, "project-create-modal", { ready: name, target: dialog });
});

test("project settings: general", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/projects/${seed.project.id}`);
  // The form renders behind a skeleton until the project has loaded.
  await expect(main.locator("#identifier")).toHaveValue(seed.project.identifier);

  await capture(page, "project-settings-general", { ready: main.locator("#identifier"), target: main });
});

test("project settings: members", async ({ asUser }) => {
  const page = await asUser("admin");
  await projectSettings(page, "members", "VR Dark");
});

test("project settings: cycles feature", async ({ asUser }) => {
  const page = await asUser("admin");
  await projectSettings(page, "features/cycles", "Enable cycles");
});

test("project settings: states", async ({ asUser }) => {
  const page = await asUser("admin");
  await projectSettings(page, "states", "Done");
});

test("project settings: labels", async ({ asUser }) => {
  const page = await asUser("admin");
  await projectSettings(page, "labels", "interface");
});

test("project settings: estimates", async ({ asUser }) => {
  const page = await asUser("admin");
  await projectSettings(
    page,
    "estimates",
    "Set up estimation systems to track and communicate the effort required for each work item."
  );
});

test("project settings: automations", async ({ asUser }) => {
  const page = await asUser("admin");
  await projectSettings(page, "automations", "Auto-archive closed work items");
});
