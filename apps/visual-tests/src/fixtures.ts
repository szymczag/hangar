/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { test as base, type BrowserContext, type Page } from "@playwright/test";
import { fixtures } from "./manifest.js";

type Personas = {
  /** Signed in. The persona decides the theme, because a signed-in user's
   *  theme comes from their stored profile and overwrites anything else. */
  asUser: (persona: "light" | "dark") => Promise<Page>;
  /** Signed in to the instance console, second factor already presented. */
  asAdmin: () => Promise<Page>;
};

async function withCookie(context: BrowserContext, name: string, value: string, baseURL: string) {
  await context.addCookies([{ name, value, url: baseURL, httpOnly: true, sameSite: "Lax" }]);
}

export const test = base.extend<Personas>({
  asUser: async ({ context, baseURL }, use) => {
    await use(async (persona) => {
      const seed = fixtures();
      const cookie = seed.users[persona]?.sessionCookie;
      if (!cookie) throw new Error(`The seed produced no session for "${persona}"`);
      await withCookie(context, "session-id", cookie, baseURL!);
      // Freeze the clock so anything rendered relative to "now" is stable.
      // `setFixedTime` rather than `install`: Date stops moving, but timers and
      // the first data fetch still run.
      const page = await context.newPage();
      await page.clock.setFixedTime(new Date(seed.clock));
      return page;
    });
  },

  asAdmin: async ({ context, baseURL }, use) => {
    await use(async () => {
      const seed = fixtures();
      const cookie = seed.users.admin?.adminSessionCookie;
      if (!cookie) throw new Error("The seed produced no console session");
      // The session middleware picks this cookie for any path containing
      // "instances", so the two coexist on one origin without colliding.
      await withCookie(context, "admin-session-id", cookie, baseURL!);
      const page = await context.newPage();
      await page.clock.setFixedTime(new Date(seed.clock));
      return page;
    });
  },
});

export { expect } from "@playwright/test";
export { fixtures };
