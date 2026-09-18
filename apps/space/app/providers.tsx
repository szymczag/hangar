/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useContext } from "react";
import { ThemeProvider } from "next-themes";
import { UNSAFE_FrameworkContext } from "react-router";
// components
import { TranslationProvider } from "@plane/i18n";
import { AppProgressBar } from "@/lib/b-progress";
import { InstanceProvider } from "@/lib/instance-provider";
import { StoreProvider } from "@/lib/store-provider";
import { ToastProvider } from "@/lib/toast-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  // The per-request nonce from entry.server.tsx, so the Content-Security-Policy
  // admits next-themes' inline anti-flash script. Only set during server render.
  const nonce = useContext(UNSAFE_FrameworkContext)?.nonce;
  return (
    <ThemeProvider themes={["light", "dark"]} defaultTheme="system" enableSystem nonce={nonce}>
      <StoreProvider>
        <AppProgressBar />
        <TranslationProvider>
          <ToastProvider>
            <InstanceProvider>{children}</InstanceProvider>
          </ToastProvider>
        </TranslationProvider>
      </StoreProvider>
    </ThemeProvider>
  );
}
