/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Banner, type BannerVariant } from "@makeplane/propel/components/banner";
import { useTranslation } from "@plane/i18n";
import { InstanceMaintenanceService } from "@plane/services";
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

// Propel's page banner carries the severity: its surface, its foreground and
// its default icon (information, warning triangle, warning circle).
const SEVERITY: Record<TMaintenanceSeverity, BannerVariant> = {
  info: "info",
  warning: "warning",
  critical: "danger",
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
  const { t } = useTranslation();

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

  const window = formatMaintenanceWindow(notice);

  return (
    // The strip keeps the 1.4 bar's 48px. Propel's page banner is 46px for a
    // one-line message, and two pixels less here would move every page under
    // it. The grid stretches the banner to the wrapper's minimum height; a
    // message that wraps still grows it.
    <div className="grid min-h-12 shrink-0">
      <Banner
        placement="page"
        variant={SEVERITY[notice.severity]}
        // Polite whatever the severity. Propel announces warning and danger
        // banners assertively, which suits an error the reader just caused, not
        // a notice that is re-rendered every minute while they work.
        role="status"
        aria-live="polite"
        title={
          <span className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:gap-3">
            <span className="line-clamp-3">{notice.message}</span>
            {window && (
              /* Tabular figures so the times line up and read as times rather
                 than as part of the sentence. */
              <span className="font-mono shrink-0 text-11 text-tertiary tabular-nums">{window}</span>
            )}
          </span>
        }
        dismissLabel={t("dismiss")}
        onDismiss={() => {
          dismissMaintenanceNotice(notice.fingerprint);
          setDismissed(notice.fingerprint);
        }}
      />
    </div>
  );
};
