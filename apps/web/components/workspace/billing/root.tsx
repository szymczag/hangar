/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { TickOutline } from "@makeplane/propel/icons";
// components
import { SettingsHeading } from "@/components/settings/heading";

export const BillingRoot = observer(function BillingRoot() {
  return (
    <section className="relative scrollbar-hide size-full overflow-y-auto">
      <SettingsHeading
        title="Hangar by @szymczag"
        description="One community edition. No subscriptions, upgrades, or paid tiers."
      />

      <div className="mt-6 overflow-hidden rounded-lg border border-subtle bg-layer-2">
        <div className="flex flex-col gap-5 px-5 py-6 sm:flex-row sm:items-start sm:px-6 sm:py-7">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-accent-primary text-on-color">
            {/* Propel has no infinity glyph, and its loop arrows read as "sync". At
                40px the glyph is as wide as the 28px icon it replaced (26px). */}
            <span className="text-40 leading-none font-semibold" aria-hidden="true">
              ∞
            </span>
          </div>

          <div className="max-w-2xl">
            <p className="tracking-wider text-caption-sm-medium text-accent-primary uppercase">Community edition</p>
            <h2 className="mt-1 text-h4-semibold text-primary">Enjoy unlimited, free, community-based Hangar.</h2>
            <p className="mt-2 text-body-sm-regular text-secondary">
              Everything implemented in this fork is available to your workspace without a license key or paid
              subscription. Your practical capacity depends only on the infrastructure operated by your administrator.
            </p>
          </div>
        </div>

        <div className="grid divide-y divide-subtle border-t border-subtle bg-layer-1 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          {["No paid tiers", "No upgrade prompts", "Community maintained"].map((benefit) => (
            <div key={benefit} className="flex items-center gap-2 px-5 py-3 text-body-sm-medium text-primary sm:px-6">
              <TickOutline className="size-4 text-accent-primary" />
              <span>{benefit}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
});
