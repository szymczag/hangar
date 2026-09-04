/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { capture, consolePage } from "../src/capture.js";
import { test } from "../src/fixtures.js";

/**
 * Every authentication screen in the instance console.
 *
 * Four of these providers are inherited from upstream and would, on their own,
 * be an odd thing for this fork to photograph. They are here because the fork
 * put config-source badges, "this setting would be ignored" refusals and the
 * secret-field behaviour into the *shared* console form components (FORK.md
 * rows 27, 35 and 51). A regression in those lands on an upstream provider page
 * exactly as readily as on OIDC or SAML.
 *
 * Captured through `<main>` rather than the viewport: the console sidebar is
 * identical on all of them, and putting it inside nineteen baselines would mean
 * one sidebar tweak touches nineteen files and review becomes a formality.
 */
const PAGES = [
  ["index", "authentication", "Allow anyone to sign up even without an invite"],
  ["github", "authentication/github", "Client ID"],
  ["gitlab", "authentication/gitlab", "Host"],
  ["google", "authentication/google", "Who may sign in with Google"],
  ["gitea", "authentication/gitea", "Gitea Host"],
  ["oidc", "authentication/oidc", "Issuer URL"],
  ["saml", "authentication/saml", "IdP entity ID"],
  ["domains", "authentication/domains", "Add a domain"],
  ["identity-import", "authentication/identity-import", "Mapping CSV"],
] as const;

for (const [name, path, readyText] of PAGES) {
  test(`the console authentication page: ${name}`, async ({ asAdmin }) => {
    const page = await asAdmin();
    const main = page.getByRole("main");

    await consolePage(page, `/god-mode/${path}`, main.getByText(readyText).first());

    await capture(page, `console-auth-${name}`, {
      ready: main.getByText(readyText).first(),
      target: main,
    });
  });
}
