import { Outlet, useLocation } from "react-router";
/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { CalendarClock } from "lucide-react";
import { Breadcrumbs, Header } from "@plane/ui";
import { BreadcrumbLink } from "@/components/common/breadcrumb-link";
import { AppHeader } from "@/components/core/app-header";
import { ContentWrapper } from "@/components/core/content-wrapper";

/**
 * One layout wraps three routes, so the crumb has to say which one you are on.
 * Derived from the path rather than passed down, because the layout renders
 * above the route that would know.
 */
function useCapacityCrumb() {
  const { pathname } = useLocation();
  if (pathname.includes("/capacity/team")) return "Team capacity";
  if (pathname.includes("/capacity/planner")) return "Workshop planner";
  // Still "Trainer capacity" rather than "My capacity": until the cutover step,
  // `/capacity` really does still show the ledger and the planner as well, and a
  // crumb that claims otherwise would be the only lie on the page.
  return "Trainer capacity";
}

function CapacityHeader() {
  const label = useCapacityCrumb();
  return (
    <Header>
      <Header.LeftItem>
        <Breadcrumbs>
          <Breadcrumbs.Item
            component={<BreadcrumbLink label={label} icon={<CalendarClock className="size-4 text-tertiary" />} />}
          />
        </Breadcrumbs>
      </Header.LeftItem>
    </Header>
  );
}

export default function CapacityLayout() {
  return (
    <>
      <AppHeader header={<CapacityHeader />} />
      <ContentWrapper>
        <Outlet />
      </ContentWrapper>
    </>
  );
}
