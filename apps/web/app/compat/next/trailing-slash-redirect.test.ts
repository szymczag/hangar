/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { createMemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { getTrailingSlashRedirect, trailingSlashRedirectMiddleware } from "./trailing-slash-redirect";

const origin = "https://hangar.example.com";

describe("getTrailingSlashRedirect", () => {
  it.each([
    [`${origin}/acme/settings`, "/acme/settings/"],
    [`${origin}/acme/settings/members`, "/acme/settings/members/"],
    [`${origin}/acme/settings/members?tab=pending`, "/acme/settings/members/?tab=pending"],
  ])("redirects %j to %j", (requestUrl, expected) => {
    expect(getTrailingSlashRedirect(requestUrl)).toBe(expected);
  });

  it.each([`${origin}/`, `${origin}/acme/settings/`, `${origin}/acme/settings/?tab=pending`])(
    "leaves %j alone",
    (requestUrl) => {
      expect(getTrailingSlashRedirect(requestUrl)).toBeNull();
    }
  );

  it("keeps the browser hash on a cold load of the same URL", () => {
    expect(
      getTrailingSlashRedirect(`${origin}/acme/browse/WEB-1?x=1`, `${origin}/acme/browse/WEB-1?x=1#comment-42`)
    ).toBe("/acme/browse/WEB-1/?x=1#comment-42");
  });

  it("does not borrow the hash of the page being navigated away from", () => {
    expect(getTrailingSlashRedirect(`${origin}/acme/settings`, `${origin}/acme/browse/WEB-1/#comment-42`)).toBe(
      "/acme/settings/"
    );
  });
});

describe("trailingSlashRedirectMiddleware", () => {
  function createRouter(initialPath: string) {
    return createMemoryRouter(
      [
        {
          id: "root",
          path: "/",
          middleware: [trailingSlashRedirectMiddleware],
          loader: () => null,
          children: [{ path: ":workspaceSlug/settings", loader: () => null }],
        },
      ],
      { initialEntries: [initialPath] }
    );
  }

  it("redirects a navigation without a trailing slash", async () => {
    const router = createRouter("/");
    await router.initialize();
    await router.navigate("/acme/settings?tab=general");
    expect(router.state.location.pathname).toBe("/acme/settings/");
    expect(router.state.location.search).toBe("?tab=general");
    router.dispose();
  });

  it("redirects the initial load without a trailing slash", async () => {
    const router = createRouter("/acme/settings");
    router.initialize();
    await new Promise<void>((resolve) => {
      const unsubscribe = router.subscribe((state) => {
        if (state.initialized && state.navigation.state === "idle") {
          unsubscribe();
          resolve();
        }
      });
    });
    expect(router.state.location.pathname).toBe("/acme/settings/");
    router.dispose();
  });

  it("lets a slashed navigation through", async () => {
    const router = createRouter("/");
    await router.initialize();
    await router.navigate("/acme/settings/");
    expect(router.state.location.pathname).toBe("/acme/settings/");
    expect(router.state.errors).toBeNull();
    router.dispose();
  });
});
