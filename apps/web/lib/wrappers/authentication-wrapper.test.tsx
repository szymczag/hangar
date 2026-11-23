/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * The set-password gate: a visitor without a session is sent to sign-in with
 * the page as next_path, and the sign-in side follows next_path only when it
 * passes isValidNextPath, so the round trip cannot be turned into an open
 * redirect. isValidNextPath is the real one from @plane/utils, not a mock.
 *
 * An account that already has a password has nothing to set: it changes the
 * password in the security settings, whether or not it has finished
 * onboarding, instead of meeting a form the API refuses (PASSWORD_ALREADY_SET).
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  user: undefined as Record<string, unknown> | undefined,
  profile: undefined as Record<string, unknown> | undefined,
  nextPath: null as string | null,
  pushed: [] as string[],
}));

vi.mock("mobx-react", () => ({ observer: (component: unknown) => component }));
vi.mock("swr", () => ({ default: () => ({ isLoading: false }) }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts/set-password",
  useSearchParams: () => ({ get: (key: string) => (key === "next_path" ? state.nextPath : null) }),
}));
// The real helper pulls in next/link for its error messages; only the enum matters here.
vi.mock("@/helpers/authentication.helper", () => ({
  EPageTypes: {
    PUBLIC: "PUBLIC",
    NON_AUTHENTICATED: "NON_AUTHENTICATED",
    SET_PASSWORD: "SET_PASSWORD",
    ONBOARDING: "ONBOARDING",
    AUTHENTICATED: "AUTHENTICATED",
  },
}));
vi.mock("@/components/common/logo-spinner", () => ({ LogoSpinner: () => null }));
vi.mock("@/hooks/store/use-workspace", () => ({ useWorkspace: () => ({ loader: false, workspaces: {} }) }));
vi.mock("@/hooks/store/user", () => ({
  useUser: () => ({ isLoading: false, data: state.user, fetchCurrentUser: async () => state.user }),
  useUserProfile: () => ({ data: state.profile }),
  useUserSettings: () => ({ data: undefined }),
}));
vi.mock("@/hooks/use-app-router", () => ({
  useAppRouter: () => ({
    push: (to: string) => state.pushed.push(to),
    replace: (to: string) => state.pushed.push(to),
  }),
}));

import { EPageTypes } from "@/helpers/authentication.helper";
import { AuthenticationWrapper } from "./authentication-wrapper";

const render = (pageType: EPageTypes) =>
  renderToStaticMarkup(
    <AuthenticationWrapper pageType={pageType}>
      <div data-testid="content" />
    </AuthenticationWrapper>
  );

describe("set-password authentication gate", () => {
  beforeEach(() => {
    state.user = undefined;
    state.profile = undefined;
    state.nextPath = null;
    state.pushed = [];
  });

  it("sends a visitor without a session to sign-in, returning to the page", () => {
    const html = render(EPageTypes.SET_PASSWORD);
    expect(html).not.toContain("content");
    expect(state.pushed).toEqual(["/?next_path=/accounts/set-password"]);
  });

  it("shows the page to a signed-in account that has no password yet", () => {
    state.user = { id: "u1", is_password_autoset: true };
    state.profile = { id: "p1", is_onboarded: true };
    const html = render(EPageTypes.SET_PASSWORD);
    expect(html).toContain("content");
    expect(state.pushed).toEqual([]);
  });

  it.each([
    ["an onboarded", { id: "p1", is_onboarded: true }],
    ["a not yet onboarded", { id: "p1", is_onboarded: false }],
  ])("sends %s account that already has a password to the security settings", (_label, profile) => {
    state.user = { id: "u1", is_password_autoset: false };
    state.profile = profile;
    const html = render(EPageTypes.SET_PASSWORD);
    expect(html).not.toContain("content");
    expect(state.pushed).toEqual(["/settings/profile/security"]);
  });

  it("sign-in follows a same-origin next_path back to the page", () => {
    state.user = { id: "u1", is_password_autoset: true };
    state.profile = { id: "p1", is_onboarded: true };
    state.nextPath = "/accounts/set-password";
    render(EPageTypes.NON_AUTHENTICATED);
    expect(state.pushed).toEqual(["/accounts/set-password"]);
  });

  it.each(["//example.com/accounts/set-password", "https://example.com/", "http:example.com", "javascript:alert(1)"])(
    "sign-in ignores the off-site next_path %s",
    (nextPath) => {
      state.user = { id: "u1", is_password_autoset: true };
      state.profile = { id: "p1", is_onboarded: true };
      state.nextPath = nextPath;
      render(EPageTypes.NON_AUTHENTICATED);
      expect(state.pushed).toEqual(["/create-workspace"]);
    }
  );
});
