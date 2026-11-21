/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { ThemeProvider } from "next-themes";
import { SWRConfig } from "swr";
import { AppProgressBar } from "@/lib/b-progress";
// local imports
import { StoreProvider } from "./store.provider";
import { InstanceProvider } from "./instance.provider";
import { UserProvider } from "./user.provider";

const DEFAULT_SWR_CONFIG = {
  refreshWhenHidden: false,
  revalidateIfStale: false,
  revalidateOnFocus: false,
  revalidateOnMount: true,
  refreshInterval: 600_000,
  errorRetryCount: 3,
};

export function CoreProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider themes={["light", "dark"]} defaultTheme="system" enableSystem>
      <AppProgressBar />
      {/* Translation and the toast viewport are mounted by the root route, under the
          prerendered HydrateFallback: see `Root` in app/root.tsx. */}
      <SWRConfig value={DEFAULT_SWR_CONFIG}>
        <StoreProvider>
          <InstanceProvider>
            <UserProvider>{children}</UserProvider>
          </InstanceProvider>
        </StoreProvider>
      </SWRConfig>
    </ThemeProvider>
  );
}
