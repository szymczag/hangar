/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */
import { createContext, useContext } from "react";
import { observer } from "mobx-react";
import { useUser } from "@/hooks/store/user";

const ViewerTimezone = createContext("UTC");
export const useViewerTimezone = () => useContext(ViewerTimezone);
export const ViewerTimezoneProvider = observer(function ViewerTimezoneProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: user } = useUser();
  return <ViewerTimezone.Provider value={user?.user_timezone || "UTC"}>{children}</ViewerTimezone.Provider>;
});
