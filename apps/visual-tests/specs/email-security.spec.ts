/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { Page } from "@playwright/test";
import { capture } from "../src/capture.js";
import { expect, test } from "../src/fixtures.js";

/**
 * Account settings → Security: Hangar's encrypted e-mail section and the
 * receipt ledger under it, and the notice the notifications tab shows while
 * encrypted delivery is required and the account has no verified key.
 *
 * The visual stack does not switch encrypted delivery on and sends no mail, so
 * only the first story reads the seeded status (no key: the upload form). The others answer the status and receipt reads here, with fixed
 * fingerprints and dates, because a verified key or a delivered message can
 * only come from a real key and a real mail provider. Nothing is typed or
 * submitted.
 */
const KEY = {
  id: "30000000-0000-4000-8000-000000000001",
  version: 1,
  primary_fingerprint: "6F3A9C41D2B87E05A1C49F7738E2D0B15C6A4E92",
  encryption_subkey_fingerprint: "A04C1E7F93B26D58C0E7A2194F6B3D85E21C07A6",
  primary_algorithm: "EdDSA",
  encryption_algorithm: "ECDH",
  encryption_key_size: 256,
  key_created_at: "2026-01-12T09:00:00Z",
  key_expires_at: "2028-01-12T09:00:00Z",
  last_validated_at: "2026-10-01T08:00:00Z",
  verified_at: "2026-10-01T08:05:00Z",
  status: "active",
  created_at: "2026-10-01T08:00:00Z",
};

const RECEIPTS = [
  {
    receipt_code: "7KQ2-M4XD-9HTR-3VBN-6WPA",
    message_id: "<20261020.0915.7kq2m4xd@mail.hangar.example>",
    mail_type: "Project notification",
    sender: "Hangar <notifications@hangar.example>",
    delivery_mode: "openpgp",
    status: "delivered",
    created_at: "2026-10-20T09:15:00Z",
    accepted_at: "2026-10-20T09:15:02Z",
    delivered_at: "2026-10-20T09:15:05Z",
    key_fingerprint: KEY.encryption_subkey_fingerprint,
  },
  {
    receipt_code: "C8FJ-2LNE-T5GW-Q1YS-0ZRU",
    message_id: "<20261018.1402.c8fj2lne@mail.hangar.example>",
    mail_type: "Sign-in code",
    sender: "Hangar <no-reply@hangar.example>",
    delivery_mode: "clear",
    status: "accepted",
    created_at: "2026-10-18T14:02:00Z",
    accepted_at: "2026-10-18T14:02:01Z",
    delivered_at: null,
    key_fingerprint: null,
  },
];

type Status = {
  enabled: boolean;
  notification_mode: "encrypted" | "in_app_only";
  active_key: typeof KEY | null;
  pending_key: typeof KEY | null;
  account_mail_encrypted: false;
  active_suppressions: string[];
};

/** Answer the receipt read, and the status read too unless `status` is null (the seeded one). */
async function answerReads(page: Page, status: Status | null, receipts: typeof RECEIPTS): Promise<void> {
  if (status) {
    await page.route(
      (url) => url.pathname.endsWith("/users/me/email-security/"),
      (route) => (route.request().method() === "GET" ? route.fulfill({ json: status }) : route.fallback())
    );
  }
  await page.route(
    (url) => url.pathname.endsWith("/users/me/email-security/receipts/"),
    (route) => (route.request().method() === "GET" ? route.fulfill({ json: { results: receipts } }) : route.fallback())
  );
}

test("account settings: encrypted email, no key", async ({ asUser }) => {
  const page = await asUser("admin");
  const main = page.getByRole("main").last();
  // The seeded status, but no receipts: whatever mail the seed queued would
  // otherwise print its own codes and times into the shot.
  await answerReads(page, null, []);

  await page.goto("/settings/profile/security");

  const section = main.getByRole("region", { name: "Encrypted email notifications" });
  const upload = section.getByRole("button", { name: "Upload public key" });
  await expect(upload).toBeVisible();

  await capture(page, "account-settings-email-security", { ready: upload, target: section });
});

test("account settings: encrypted email, verified key", async ({ asUser }) => {
  const page = await asUser("admin");
  const main = page.getByRole("main").last();
  await answerReads(
    page,
    {
      enabled: true,
      notification_mode: "encrypted",
      active_key: KEY,
      pending_key: null,
      account_mail_encrypted: false,
      active_suppressions: [],
    },
    []
  );

  await page.goto("/settings/profile/security");

  const section = main.getByRole("region", { name: "Encrypted email notifications" });
  const fingerprint = section.getByText("6F3A 9C41 D2B8 7E05 A1C4 9F77 38E2 D0B1 5C6A 4E92", { exact: true });
  await expect(fingerprint).toBeVisible();
  await expect(section.getByText("No email receipts are available yet.")).toBeVisible();

  await capture(page, "account-settings-email-security-key", { ready: fingerprint, target: section });
});

test("account settings: email receipts", async ({ asUser }) => {
  const page = await asUser("admin");
  const main = page.getByRole("main").last();
  await answerReads(
    page,
    {
      enabled: true,
      notification_mode: "encrypted",
      active_key: KEY,
      pending_key: null,
      account_mail_encrypted: false,
      active_suppressions: [],
    },
    RECEIPTS
  );

  await page.goto("/settings/profile/security");

  const ledger = main.getByRole("region", { name: "Verify a Hangar email" });
  const receipt = ledger.getByText(RECEIPTS[1].receipt_code, { exact: true });
  await expect(receipt).toBeVisible();

  await capture(page, "account-settings-email-receipts", { ready: receipt, target: ledger });
});

test("account settings: the encrypted email notice on notifications", async ({ asUser }) => {
  const page = await asUser("admin");
  const main = page.getByRole("main").last();
  await answerReads(
    page,
    {
      enabled: true,
      notification_mode: "in_app_only",
      active_key: null,
      pending_key: null,
      account_mail_encrypted: false,
      active_suppressions: [],
    },
    []
  );

  await page.goto("/settings/profile/notifications");

  const notice = main.getByRole("alert").filter({ hasText: "Add and verify an OpenPGP key" });
  const action = notice.getByRole("button", { name: "Set up encrypted email" });
  await expect(action).toBeVisible();

  await capture(page, "account-settings-email-security-notice", { ready: action, target: notice });
});
