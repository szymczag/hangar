/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { AlertOctagon, AlertTriangle, Info } from "lucide-react";
import useSWR from "swr";
import { InstanceMaintenanceService } from "@plane/services";
import { Banner } from "@plane/propel/banner";
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

// The propel variants carry raw palette values under a standing TODO; the
// severity is expressed here in the semantic tokens the rest of the app uses.
const SEVERITY: Record<
  TMaintenanceSeverity,
  { variant: "info" | "warning" | "error"; surface: string; rule: string; icon: typeof Info }
> = {
  info: { variant: "info", surface: "bg-accent-subtle", rule: "border-l-accent-strong", icon: Info },
  warning: { variant: "warning", surface: "bg-warning-subtle", rule: "border-l-warning-strong", icon: AlertTriangle },
  critical: { variant: "error", surface: "bg-danger-subtle", rule: "border-l-danger-strong", icon: AlertOctagon },
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

  const { variant, surface, rule, icon: Icon } = SEVERITY[notice.severity];
  const window = formatMaintenanceWindow(notice);

  return (
    <Banner
      role="status"
      aria-live="polite"
      variant={variant}
      dismissible
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
      className={cn(
        // The propel container is a fixed h-12 centred row; a message that
        // wraps needs to grow, and to align to the top when it does.
        // Per-side colours on purpose: `border-subtle` and the severity rule
        // are the same tailwind-merge group, so a bare `border-<colour>` would
        // repaint all four sides and lose the hairline under the strip.
        "h-auto min-h-12 shrink-0 items-start gap-3 border-b border-l-[3px] border-b-subtle px-4 py-2.5 sm:px-6",
        surface,
        rule
      )}
    />
  );
};
