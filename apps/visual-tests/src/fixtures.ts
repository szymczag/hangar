/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { test as base, type BrowserContext, type Page } from "@playwright/test";
import { fixtures } from "./manifest.js";

type Personas = {
  /** Signed in to the web application. The persona decides the theme, because a
   *  signed-in user's theme comes from their stored profile and overwrites
   *  anything else -- and, for "admin", the workspace role: several settings
   *  pages render "you are not authorized" for an ordinary member. */
  asUser: (persona: "light" | "dark" | "admin") => Promise<Page>;
  /** Signed in to the instance console, second factor already presented. */
  asAdmin: () => Promise<Page>;
};

async function withCookie(context: BrowserContext, name: string, value: string, baseURL: string) {
  await context.addCookies([{ name, value, url: baseURL, httpOnly: true, sameSite: "Lax" }]);
}

/**
 * Report any request that would change seeded state.
 *
 * With `fullyParallel` and thirty-odd specs sharing one stack, a single test
 * that writes makes every other test order-dependent -- and the symptom of that
 * is indistinguishable from flakiness, which this suite has already spent
 * enough time chasing.
 *
 * Deliberately reporting rather than failing, for now. The boot path shows no
 * writes and the one server-side write that does happen is triggered by a GET,
 * so this is expected to stay silent; but "expected to pass" is a reason to
 * measure rather than to assume, and turning a wrong assumption into a hard
 * failure would break every spec at once. Promote it to a throw once CI has
 * shown it quiet across a soak.
 */
async function reportWrites(context: BrowserContext): Promise<void> {
  await context.route("**/api/**", async (route, request) => {
    const method = request.method();
    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
      console.warn(`[write-guard] ${method} ${request.url()}`);
    }
    await route.fallback();
  });
}

export const test = base.extend<Personas>({
  asUser: async ({ context, baseURL }, use) => {
    await use(async (persona) => {
      const seed = fixtures();
      const cookie = seed.users[persona]?.sessionCookie;
      if (!cookie) throw new Error(`The seed produced no session for "${persona}"`);
      await withCookie(context, "session-id", cookie, baseURL!);
      await reportWrites(context);
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
      await reportWrites(context);
      const page = await context.newPage();
      await page.clock.setFixedTime(new Date(seed.clock));
      return page;
    });
  },
});

export { expect } from "@playwright/test";
export { fixtures };
