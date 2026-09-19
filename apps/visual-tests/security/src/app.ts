/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { expect, type APIRequestContext, type BrowserContext } from "@playwright/test";
import { fixtures } from "../../src/manifest.js";
import { trustedTypesMode, type TObservation } from "./enforce";

// What the security specs share: the seeded workspace, a signed-in user,
// content the editor has to keep, and writes through the API.

export const seed = fixtures();
export const slug = seed.workspace.slug;
export const projectId = seed.project.id;

/** Every formatting feature whose markup the policies must leave intact. */
export const RICH_DESCRIPTION = [
  '<h2>Heading</h2><p data-text-align="center">centred paragraph</p>',
  '<p><strong>bold</strong> <em>italic</em> <span data-text-color="gray">gray</span> ',
  '<span data-background-color="peach">peach</span> <a href="https://example.com/doc">a link</a></p>',
  "<ul><li><p>bullet</p></li></ul><ol><li><p>numbered</p></li></ol>",
  '<ul data-type="taskList"><li data-type="taskItem" data-checked="true"><label><input type="checkbox" checked><span></span></label><div><p>task</p></div></li></ul>',
  '<blockquote><p>quoted</p></blockquote><pre><code class="language-ts">const x = 1;</code></pre><hr>',
  '<table><tbody><tr><th data-background-color="green"><p>head</p></th><th><p>plain</p></th></tr>',
  '<tr><td background="var(--editor-colors-purple-background)"><p>legacy cell</p></td><td><p>cell</p></td></tr></tbody></table>',
  // A callout as the editor stores it: its emoji is drawn from the Unicode
  // value, and the URL beside it must never be loaded as an image.
  '<div data-block-type="callout-component" data-logo-in-use="emoji" data-emoji-unicode="128161" ',
  'data-emoji-url="https://cdn.jsdelivr.net/npm/emoji-datasource-apple/img/apple/64/1f4a1.png" data-background="green">',
  "<p>callout</p></div>",
  "<p>last paragraph</p>",
].join("");

export async function signIn(context: BrowserContext, baseURL: string) {
  await context.addCookies([
    { name: "session-id", value: seed.users.light.sessionCookie!, url: baseURL, httpOnly: true, sameSite: "Lax" },
  ]);
}

/** Headers for a write through the API as the signed-in user. */
export async function writeHeaders(request: APIRequestContext, baseURL: string) {
  const { csrf_token: csrf } = await (await request.get("/auth/get-csrf-token/")).json();
  return { "X-CSRFToken": csrf as string, Referer: `${baseURL}/` };
}

export async function post(request: APIRequestContext, baseURL: string, path: string, data: unknown) {
  const response = await request.post(path, { headers: await writeHeaders(request, baseURL), data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBe(true);
  return response.json();
}

export const createWorkItem = (request: APIRequestContext, baseURL: string, name: string) =>
  post(request, baseURL, `/api/workspaces/${slug}/projects/${projectId}/issues/`, {
    name,
    description_html: RICH_DESCRIPTION,
  });

/**
 * What the default policy may report: only hostile markup (event handlers),
 * reported as observed or as removed depending on the mode under test.
 */
export function expectOnlyHostileObservations(observations: TObservation[]) {
  const enforcing = trustedTypesMode() === "enforce";
  for (const observation of observations) {
    expect(observation.disposition).toBe(enforcing ? "enforce" : "observe");
    expect(observation["violated-directive"]).toBe(enforcing ? "html-changed" : "html-would-change");
    expect(observation["script-sample"]).toMatch(/onerror|onload/);
  }
}
