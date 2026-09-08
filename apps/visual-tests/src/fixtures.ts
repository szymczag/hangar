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

/** A request that would have changed the seeded state. */
type Write = { method: string; url: string };

/**
 * Refuse any request that would change seeded state.
 *
 * With `fullyParallel` and thirty-odd specs sharing one stack, a single test
 * that writes makes every other test order-dependent -- and the symptom of that
 * is indistinguishable from flakiness, which this suite has already spent
 * enough time chasing. The guard exists to turn a week of misdiagnosis into a
 * line naming the request.
 *
 * This landed reporting rather than failing, because "expected to pass" is a
 * reason to measure rather than to assume, and a wrong assumption here would
 * have broken every spec at once. The soak settled it: five iterations of the
 * full suite, no write observed. So it fails now.
 *
 * The request is aborted rather than allowed through. A write that lands
 * corrupts the stack the remaining specs are still photographing, and the
 * failure would then be reported against a fixture set that is already wrong.
 *
 * Known blind spot: this sees what the *browser* sends. The one server-side
 * write on the boot path is triggered by a GET and stays invisible to it.
 */
async function guardWrites(context: BrowserContext, writes: Write[]): Promise<void> {
  await context.route("**/api/**", async (route, request) => {
    const method = request.method();
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
      await route.fallback();
      return;
    }
    writes.push({ method, url: request.url() });
    await route.abort("blockedbyclient");
  });
}

export const test = base.extend<Personas & { writeGuard: void }>({
  /** Automatic, so a spec that never asks for a persona is still covered. */
  writeGuard: [
    async ({ context }, use) => {
      const writes: Write[] = [];
      await guardWrites(context, writes);
      await use();
      if (writes.length === 0) return;
      throw new Error(
        [
          `This test sent ${writes.length} request(s) that would change seeded state:`,
          "",
          ...writes.map((write) => `  ${write.method} ${write.url}`),
          "",
          "Every spec here shares one seeded stack, so a write makes every other",
          "spec order-dependent, and that reads as flakiness rather than as a",
          "state bug. Photograph what the seed produced; do not create it from",
          "the browser.",
        ].join("\n")
      );
    },
    { auto: true },
  ],

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
