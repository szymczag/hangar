// Copyright (c) 2026-present Maciej Szymczak and contributors
// SPDX-License-Identifier: AGPL-3.0-only

import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import test from "node:test";

const repoRoot = new URL("../", import.meta.url);
const billingComponents = new URL("../apps/web/core/components/workspace/billing/", import.meta.url);
const billingRoot = readFileSync(new URL("root.tsx", billingComponents), "utf8");

// The edition name is defined once, in the dialog that is named after it. Read
// it from there rather than repeating the literal, so a rename cannot leave the
// locales and the code disagreeing about what this build is called.
const editionName = /HANGAR_EDITION_NAME = "([^"]+)"/.exec(
  readFileSync(new URL("../apps/web/ce/components/license/modal/community-modal.tsx", import.meta.url), "utf8")
)?.[1];

test("keeps the former billing route static and community focused", () => {
  assert.match(billingRoot, /Enjoy unlimited, free, community-based Hangar\./);
  assert.match(billingRoot, /practical capacity depends only on the infrastructure/);
  assert.match(billingRoot, /No paid tiers/);

  assert.doesNotMatch(billingRoot, /onClick|<Button|window\.open|useState/);
  assert.doesNotMatch(billingRoot, /PlansComparison|BillingFrequency|SUBSCRIPTION_/);
  assert.doesNotMatch(billingRoot, /Upgrade to|Talk to Sales|monthlyPrice|yearlyPrice/i);
});

test("does not ship the removed commercial comparison components", () => {
  const componentFiles = readdirSync(billingComponents, { recursive: true })
    .filter((entry) => typeof entry === "string" && entry.endsWith(".tsx"))
    .map((entry) => readFileSync(new URL(entry, billingComponents), "utf8"))
    .join("\n");

  assert.doesNotMatch(componentFiles, /PlansComparison|PlanFrequencyToggle|Upgrade to|Talk to Sales/i);
});

test("labels the settings entry with the edition name in every locale", () => {
  assert.ok(editionName, "HANGAR_EDITION_NAME must be exported from the community modal");

  const localesDirectory = new URL("../packages/i18n/src/locales/", import.meta.url);
  const locales = readdirSync(localesDirectory, { withFileTypes: true }).filter((entry) => entry.isDirectory());

  for (const locale of locales) {
    const workspaceSettingsUrl = new URL(`${locale.name}/workspace-settings.json`, localesDirectory);
    if (!existsSync(workspaceSettingsUrl)) continue;

    const workspaceSettings = JSON.parse(readFileSync(workspaceSettingsUrl, "utf8"));
    assert.equal(
      workspaceSettings.workspace_settings.settings.billing_and_plans.title,
      editionName,
      `${locale.name} still exposes a commercial billing label`
    );
  }

  const page = readFileSync(
    new URL("apps/web/app/(all)/[workspaceSlug]/(settings)/settings/(workspace)/billing/page.tsx", repoRoot),
    "utf8"
  );
  assert.ok(page.includes(editionName));
  assert.doesNotMatch(page, /Billing & Plans/);
});
