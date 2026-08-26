/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import { AuthRoot } from "@/components/account/auth-forms/auth-root";
import type { EAuthModes } from "@/helpers/authentication.helper";
import { useInstance } from "@/hooks/store/use-instance";
import { AuthFooter } from "./footer";
import { AuthHeader } from "./header";

type AuthBaseProps = {
  authType: EAuthModes;
};

export const AuthBase = observer(function AuthBase({ authType }: AuthBaseProps) {
  const { config } = useInstance();
  // Both values are validated as plain hex colours by the API, on write and
  // again on read, so what arrives here is safe to place in a style attribute —
  // which matters more on this page than on any other, because this is the one
  // that collects passwords.
  const backdropColor = config?.login_backdrop_color;
  const backgroundUrl = config?.login_background_url;
  const accentColor = config?.accent_color;

  return (
    <div
      className="relative z-10 flex h-screen w-screen flex-col items-center overflow-hidden overflow-y-auto bg-cover bg-center px-8 pt-6 pb-10"
      style={{
        ...(backdropColor ? { backgroundColor: backdropColor } : {}),
        ...(backgroundUrl ? { backgroundImage: `url("${backgroundUrl}")` } : {}),
        // --brand-default is what the accent tokens derive from, so overriding
        // it here recolours the sign-in button, links and focus borders in one
        // move, and only within this subtree.
        ...(accentColor ? ({ "--brand-default": accentColor } as React.CSSProperties) : {}),
      }}
    >
      <AuthHeader type={authType} />
      <AuthRoot authMode={authType} />
      <AuthFooter />
    </div>
  );
});
