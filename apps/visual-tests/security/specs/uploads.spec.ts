/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, test, type Page } from "@playwright/test";
import { post, projectId, seed, signIn, slug } from "../src/app";
import { attachDiagnostics, enforceContentSecurityPolicy, watch } from "../src/enforce";

// Adding a screenshot to a work item: the browser posts the file to object
// storage through a presigned URL and shows it from there. Both have to stay
// on this instance's origin, which is all connect-src and img-src allow.

/** A 64x40 PNG, the size of nothing in particular. */
const SCREENSHOT =
  "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAoCAIAAADBrGu+AAAAV0lEQVR4nO3PQQkAMAzAwAqrfyZrIvY4BoEIuMzZ/brhgga0oAEtaEALGtCCBrSgAS1oQAsa0IIGtKABLWhACxrQgga0oAEtaEALGtCCBrSgAS1oQAseu6I+gLWOzJlMAAAAAElFTkSuQmCC";

test.beforeEach(async ({ context }) => {
  await enforceContentSecurityPolicy(context);
});

test.afterEach(async ({ page }, testInfo) => {
  await attachDiagnostics(page, testInfo);
});

/** The images in the description that have loaded, by source. */
const loadedImages = (page: Page) =>
  page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLImageElement>(".ProseMirror img"))
      .filter((image) => image.complete && image.naturalWidth > 0)
      .map((image) => image.src)
  );

test("a screenshot pasted into a description is stored and shown from this instance", async ({
  page,
  context,
  baseURL,
}) => {
  await signIn(context, baseURL!);
  const workItem = await post(context.request, baseURL!, `/api/workspaces/${slug}/projects/${projectId}/issues/`, {
    name: "Uploads: pasted screenshot",
    description_html: "<p>the screenshot goes here</p>",
  });
  const reports = watch(page);
  const url = `/${slug}/browse/${seed.project.identifier}-${workItem.sequence_id}/`;

  await page.goto(url);
  await page.locator(".ProseMirror").first().getByText("the screenshot goes here").click();
  await page.evaluate((png) => {
    const transfer = new DataTransfer();
    const bytes = Uint8Array.from(atob(png), (character) => character.charCodeAt(0));
    transfer.items.add(new File([bytes], "screenshot.png", { type: "image/png" }));
    document
      .querySelector(".ProseMirror")!
      .dispatchEvent(new ClipboardEvent("paste", { clipboardData: transfer, bubbles: true, cancelable: true }));
  }, SCREENSHOT);

  // Uploaded, not just previewed: the preview is a data: URL.
  await expect
    .poll(async () => (await loadedImages(page)).filter((source) => !source.startsWith("data:")).length)
    .toBe(1);
  await expect
    .poll(async () => {
      const response = await context.request.get(
        `/api/workspaces/${slug}/projects/${projectId}/issues/${workItem.id}/`
      );
      return (await response.json()).description_html as string;
    })
    .toMatch(/<image-component[^>]+src="[0-9a-f-]{36}"/);
  await reports.expectClean();

  // And shown from storage when the work item is opened again.
  await page.reload();
  await expect.poll(async () => (await loadedImages(page)).length).toBe(1);
  expect(new URL((await loadedImages(page))[0]).origin).toBe(new URL(baseURL!).origin);
  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});

test("a screenshot attached to a work item is uploaded", async ({ page, context, baseURL }) => {
  await signIn(context, baseURL!);
  const workItem = await post(context.request, baseURL!, `/api/workspaces/${slug}/projects/${projectId}/issues/`, {
    name: "Uploads: attachment",
  });
  const reports = watch(page);

  await page.goto(`/${slug}/browse/${seed.project.identifier}-${workItem.sequence_id}/`);
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "screenshot.png",
      mimeType: "image/png",
      buffer: Buffer.from(SCREENSHOT, "base64"),
    });
  await expect
    .poll(async () => {
      const response = await context.request.get(
        `/api/assets/v2/workspaces/${slug}/projects/${projectId}/issues/${workItem.id}/attachments/`
      );
      return response.ok()
        ? ((await response.json()) as { attributes?: { name?: string } }[]).map((a) => a.attributes?.name)
        : [];
    })
    .toContain("screenshot.png");

  await reports.expectClean();
  expect(reports.observations).toEqual([]);
});
