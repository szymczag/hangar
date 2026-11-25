/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture } from "../src/capture.js";
import { expect, fixtures, test } from "../src/fixtures.js";

/**
 * The Todoist import history.
 *
 * Two things have to be true before this renders anything at all, and only one
 * of them is a database row. The screen is gated on
 * `config.is_todoist_imports_enabled`, which comes from the `TODOIST_IMPORTS_ENABLED`
 * process environment rather than from instance configuration -- so the compose
 * file sets it, and no amount of seeding would have been enough.
 *
 * The seeded jobs are deliberately both terminal. An active one makes this
 * component poll every three seconds and render a spinning loader; finished rows
 * give a static DOM and still show everything worth photographing -- the status
 * icons, the task tallies, the retry action on a failure, the report link on
 * both.
 */
test("the workspace import history", async ({ asUser }) => {
  // Admin: the screen refuses an ordinary member outright.
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/imports`);

  // The report link exists only for a job that actually finished. The "Recent
  // imports" heading would have been the obvious choice and is the wrong one:
  // it renders in the loading, empty and error states too.
  const report = main.getByRole("link", { name: /download report/i }).first();
  await expect(report).toBeVisible();
  await expect(main.getByText(/Completed · 128 of 128 tasks/)).toBeVisible();
  await expect(main.getByText(/Failed · 41 of 64/)).toBeVisible();

  // The history section, not the whole page. `main` here is taller than the
  // viewport, so a page-scoped shot clipped the failed row off the bottom --
  // photographing one and a half of the two rows the story asserts. Scoping
  // also leaves the upload wizard out, which is a different surface with a file
  // input in it.
  //
  // The innermost section holding the heading, rather than a fixed number of
  // ancestors: the Propel move wrapped the heading in `SettingsHeading`, and
  // "two levels up" then photographed the heading alone.
  const history = main
    .locator("section")
    .filter({ has: page.getByRole("heading", { name: "Recent imports" }) })
    .last();
  await capture(page, "workspace-imports", { ready: report, target: history });
});

/**
 * The Todoist upload form: the three steps, the destination project and the
 * file drop.
 *
 * Nothing is chosen, so the preview button is the disabled one and no request
 * leaves the browser. The section holding the file input, not the page, so the
 * history below (its own story) does not move this one.
 */
test("the Todoist import upload form", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.goto(`/${seed.workspace.slug}/settings/imports`);

  const preview = main.getByRole("button", { name: "Preview import" });
  await expect(preview).toBeVisible();
  await expect(preview).toBeDisabled();

  const form = main
    .locator("section")
    .filter({ has: page.locator('input[type="file"]') })
    .first();
  await capture(page, "workspace-imports-upload", { ready: preview, target: form });
});

/**
 * The Todoist review step, with every part it can show.
 *
 * Reaching it takes a preview, which is a POST the write guard would refuse, so
 * the story answers it in the browser and nothing reaches the server: the
 * request is fulfilled here with a manifest that carries an error and a warning,
 * an assignee to map, a section that collides with an existing module, the
 * module and project note notices, and the duplicate confirmation. The preview
 * token in it is never rendered; the screen only sends it back on import, which
 * the story does not press.
 */
test("the Todoist import review", async ({ asUser }) => {
  const page = await asUser("admin");
  const seed = fixtures();
  const main = page.getByRole("main").last();

  await page.route(
    (url) => url.pathname.endsWith("/imports/todoist/preview/"),
    async (route) => {
      await route.fulfill({
        json: {
          digest: "vr-digest",
          preview_token: "vr-preview-token",
          counts: { task: 42, section: 3, note: 5 },
          diagnostics: [
            {
              level: "error",
              code: "invalid_date",
              message: "The due date could not be read.",
              row: 12,
              field: "DATE",
            },
            {
              level: "warning",
              code: "unknown_priority",
              message: "Priority 5 is not a Todoist priority; it is imported as none.",
              row: 7,
              field: "PRIORITY",
            },
          ],
          assignees: ["Ada Lovelace"],
          module_conflicts: [{ row: 4, name: seed.module.name, module_id: seed.module.id }],
          project_note_action: "skip",
          enables_modules: true,
          duplicate: true,
        },
      });
    }
  );

  await page.goto(`/${seed.workspace.slug}/settings/imports`);

  // The project select's trigger shows its placeholder until something is
  // chosen; clicking the text opens it whatever element carries it.
  await main.getByText("Select a project").first().click();
  await page
    .getByRole("option", { name: new RegExp(`^${seed.project.identifier} · `) })
    .first()
    .click();
  await main.locator('input[type="file"]').setInputFiles({
    name: "todoist.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("TYPE,CONTENT\ntask,Write the agenda\n"),
  });
  await main.getByRole("button", { name: "Preview import" }).click();

  const heading = main.getByRole("heading", { name: "Import manifest" });
  await expect(heading).toBeVisible();
  await expect(main.getByText("The due date could not be read.")).toBeVisible();
  await expect(main.getByText("Ada Lovelace")).toBeVisible();

  const review = main.locator("section").filter({ has: heading }).last();
  await capture(page, "workspace-imports-review", { ready: heading, target: review });
});
