/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * /accounts/set-password is where a signed-in account without a password of
 * its own (is_password_autoset, e.g. created by magic code) chooses one.
 *
 * The page used to render the reset-password form, which needs the uidb64 and
 * token of a reset email; without them it posted to
 * /auth/reset-password/undefined/undefined/ and could only ever fail. The
 * set-password form posts to /auth/set-password/ on the session instead.
 *
 * The page must also not offer a password to an account bound to an identity
 * provider (the API answers 403 PASSWORD_MANAGED_BY_IDENTITY_PROVIDER) or on an
 * instance where password sign-in is off, the same rule as onboarding.
 */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  user: undefined as Record<string, unknown> | undefined,
  config: { is_email_password_enabled: true } as Record<string, unknown> | undefined,
  pageType: undefined as string | undefined,
  header: undefined as { pageTitle: string; additionalAction?: unknown } | undefined,
}));

vi.mock("mobx-react", () => ({ observer: (component: unknown) => component }));
vi.mock("@makeplane/propel/icons", () => ({ ShieldOutline: () => null }));
vi.mock("@plane/i18n", () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock("@/layouts/default-layout", () => ({
  default: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));
vi.mock("@/lib/wrappers/authentication-wrapper", () => ({
  AuthenticationWrapper: ({ children, pageType }: React.PropsWithChildren<{ pageType: string }>) => {
    state.pageType = pageType;
    return <>{children}</>;
  },
}));
vi.mock("@/helpers/authentication.helper", () => ({ EPageTypes: { SET_PASSWORD: "SET_PASSWORD" } }));
vi.mock("@/components/auth-screens/header", () => ({
  AuthHeader: () => <div data-testid="auth-switch-header" />,
  AuthHeaderBase: (props: { pageTitle: string; additionalAction?: unknown }) => {
    state.header = props;
    return null;
  },
}));
vi.mock("@/components/account/auth-forms/set-password", () => ({
  SetPasswordForm: () => <div data-testid="set-password-form" />,
}));
vi.mock("@/components/account/auth-forms/reset-password", () => ({
  ResetPasswordForm: () => <div data-testid="reset-password-form" />,
}));
vi.mock("@/components/account/auth-forms/common/container", () => ({
  FormContainer: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
}));
vi.mock("@/hooks/store/user", () => ({ useUser: () => ({ data: state.user }) }));
vi.mock("@/hooks/store/use-instance", () => ({ useInstance: () => ({ config: state.config }) }));

import SetPasswordPage from "./page";

const render = () => renderToStaticMarkup(<SetPasswordPage />);

describe("/accounts/set-password", () => {
  beforeEach(() => {
    state.user = { id: "u1", email: "user@example.com", is_password_autoset: true, is_federated: false };
    state.config = { is_email_password_enabled: true };
    state.pageType = undefined;
    state.header = undefined;
  });

  it("does not offer a signed-in visitor the sign-up or sign-in switch", () => {
    const html = render();
    expect(html).not.toContain('data-testid="auth-switch-header"');
    expect(state.header).toEqual({ pageTitle: "auth.set_password.title" });
  });

  it("is gated by the set-password authentication rule", () => {
    render();
    expect(state.pageType).toBe("SET_PASSWORD");
  });

  it("renders the set-password form, not the token-bound reset form", () => {
    const html = render();
    expect(html).toContain('data-testid="set-password-form"');
    expect(html).not.toContain('data-testid="reset-password-form"');
  });

  it("offers no password to an account bound to an identity provider", () => {
    state.user = { ...state.user, is_federated: true };
    const html = render();
    expect(html).not.toContain('data-testid="set-password-form"');
    expect(html).not.toContain('data-testid="reset-password-form"');
    expect(html).toContain("identity provider");
  });

  it("offers no password where password sign-in is switched off", () => {
    state.config = { is_email_password_enabled: false };
    const html = render();
    expect(html).not.toContain('data-testid="set-password-form"');
    expect(html).toContain("Password sign-in is switched off");
  });
});
