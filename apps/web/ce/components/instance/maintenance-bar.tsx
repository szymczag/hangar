/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Banner } from "@makeplane/propel/components/banner";
import { AlertOctagonOutline, InfoOutline, WarningTriangleOutline } from "@makeplane/propel/icons";
import { InstanceMaintenanceService } from "@plane/services";
import { cn } from "@plane/utils";
// helpers
import {
  asMaintenanceNotice,
  dismissMaintenanceNotice,
  dismissedMaintenanceFingerprint,
  formatMaintenanceWindow,
  recalledMaintenanceNotice,
  rememberMaintenanceNotice,
  type TMaintenanceNotice,
  type TMaintenanceSeverity,
} from "@/helpers/maintenance-notice";

const service = new InstanceMaintenanceService();

// The Propel variant carries the surface (accent, warning or danger subtle, as
// before); the severity rule down the leading edge is Hangar's own, drawn by the
// wrapper because the banner takes no class names.
const SEVERITY: Record<
  TMaintenanceSeverity,
  { variant: "accent" | "warning" | "danger"; rule: string; icon: typeof InfoOutline }
> = {
  info: { variant: "accent", rule: "border-l-accent-strong", icon: InfoOutline },
  warning: { variant: "warning", rule: "border-l-warning-strong", icon: WarningTriangleOutline },
  critical: { variant: "danger", rule: "border-l-danger-strong", icon: AlertOctagonOutline },
};

/**
 * The strip an operator raises to announce downtime.
 *
 * It polls on its own rather than riding `/api/instances/`, which is cached for
 * two hours and fetched once per tab: an announcement that only reaches people
 * who reload is not an announcement.
 *
 * With no notice this renders `null`, and the layout above it is unchanged.
 */
export const MaintenanceBar = () => {
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [recalled, setRecalled] = useState<TMaintenanceNotice | null>(null);

  // Read storage after mount: the server render has no window, and reading it
  // during render would make the first client paint disagree with the markup.
  useEffect(() => {
    setDismissed(dismissedMaintenanceFingerprint());
    setRecalled(recalledMaintenanceNotice());
  }, []);

  const { data } = useSWR("INSTANCE_MAINTENANCE_NOTICE", () => service.retrieve(), {
    refreshInterval: 60_000,
    // Someone back at their desk after lunch should see the notice at once,
    // not up to a minute later.
    revalidateOnFocus: true,
    revalidateOnReconnect: true,
    shouldRetryOnError: false,
  });

  const notice = useMemo(() => {
    if (data === undefined) return recalled;
    const fresh = asMaintenanceNotice(data.notice);
    return fresh;
  }, [data, recalled]);

  useEffect(() => {
    // Only once an answer has actually arrived; an unreachable API must not
    // erase the notice it last gave us.
    if (data !== undefined) rememberMaintenanceNotice(asMaintenanceNotice(data.notice));
  }, [data]);

  if (!notice || notice.fingerprint === dismissed) return null;

  const { variant, rule, icon: Icon } = SEVERITY[notice.severity];
  const window = formatMaintenanceWindow(notice);

  return (
    // The page banner draws its own hairline underneath; the wrapper adds only
    // the severity rule down the leading edge.
    <div className={cn("shrink-0 border-l-[3px]", rule)}>
      <Banner
        // The variant would make a warning or a critical notice an `alert`; this
        // is an announcement read when convenient, so it stays a polite status.
        role="status"
        aria-live="polite"
        placement="page"
        variant={variant}
        dismissLabel="Dismiss banner"
        onDismiss={() => {
          dismissMaintenanceNotice(notice.fingerprint);
          setDismissed(notice.fingerprint);
        }}
        icon={<Icon className="size-4 shrink-0 text-secondary" aria-hidden="true" />}
        title={
          <span className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-3">
            <span className="line-clamp-3 text-13 leading-5 text-primary">{notice.message}</span>
            {window && (
              /* Tabular figures so the times line up and read as times rather
                 than as part of the sentence. */
              <span className="font-mono shrink-0 text-11 text-tertiary tabular-nums">{window}</span>
            )}
          </span>
        }
      />
    </div>
  );
};
