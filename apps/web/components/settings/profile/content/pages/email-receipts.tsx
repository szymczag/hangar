/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import type { IEmailReceipt } from "@plane/types";
import { Badge } from "@makeplane/propel/components/badge";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { InputField } from "@makeplane/propel/components/input-field";
import { MailXOutline, SearchOutline, TickCircleOutline } from "@makeplane/propel/icons";
import { SettingsHeading } from "@/components/settings/heading";
import { UserService } from "@/services/user.service";

const userService = new UserService();
const TIMESTAMP_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : `${TIMESTAMP_FORMATTER.format(date)} UTC`;
};

const stateLabel = (receipt: IEmailReceipt) => {
  if (receipt.delivery_mode === "suppressed") return "Not sent";
  if (receipt.status === "delivered") return "Delivered";
  if (receipt.status === "accepted") return "Accepted by provider";
  if (receipt.status === "acceptance_unknown") return "Provider response unknown";
  if (receipt.status.startsWith("failed")) return "Delivery failed";
  if (receipt.status === "processing") return "Sending";
  return "Queued";
};

const protectionLabel = (receipt: IEmailReceipt) => {
  if (receipt.delivery_mode === "suppressed") return "Not sent";
  if (receipt.delivery_mode === "openpgp") return "OpenPGP encrypted";
  return "Unencrypted account email";
};

export const EmailReceiptLedger = () => {
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const { data, isLoading } = useSWR(["CURRENT_USER_EMAIL_RECEIPTS", appliedQuery], () =>
    userService.getEmailReceipts(appliedQuery || undefined)
  );

  const verify = () => setAppliedQuery(query.trim().toUpperCase());
  const rows = data?.results ?? [];

  return (
    <section className="mt-10 border-t border-subtle pt-8" aria-labelledby="email-receipts-title">
      <SettingsHeading
        variant="h4"
        title={<span id="email-receipts-title">Verify a Hangar email</span>}
        description="Every legitimate message contains a Hangar email receipt. Match that code here before following an unexpected link or opening an attachment. This ledger never stores the email body."
      />

      <div className="mt-5 flex max-w-xl items-start gap-2">
        <div className="[&_input]:font-mono flex-1 [&_input]:uppercase">
          <InputField
            size="lg"
            orientation="vertical"
            aria-label="Hangar email receipt"
            value={query}
            onChange={(event) => setQuery(event.target.value.toUpperCase())}
            onKeyDown={(event) => event.key === "Enter" && verify()}
            placeholder="ABCD-EF12-3456-7890-ABCD"
          />
        </div>
        <Button
          variant="secondary"
          size="lg"
          stretch="auto"
          icon={<Icon icon={SearchOutline} />}
          label="Verify"
          onClick={verify}
          disabled={!query.trim()}
        />
      </div>

      <div className="mt-5 max-w-3xl overflow-hidden rounded-lg border border-subtle bg-layer-1">
        {isLoading ? (
          <div className="h-28 animate-pulse bg-layer-2" aria-label="Loading email receipts" />
        ) : rows.length === 0 ? (
          <div className="flex gap-3 p-5 text-body-xs-regular text-secondary">
            <MailXOutline className="mt-0.5 size-4 shrink-0" />
            <p>
              {appliedQuery
                ? "No Hangar email matches this receipt. Treat the message as suspicious."
                : "No email receipts are available yet."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-subtle">
            {rows.map((receipt) => (
              <li key={receipt.receipt_code} className="grid gap-3 p-4 text-body-xs-regular sm:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <TickCircleOutline className="size-4 shrink-0 text-success-primary" />
                    <span className="text-body-xs-medium text-primary">{receipt.mail_type}</span>
                    <Badge
                      size="sm"
                      variant={receipt.delivery_mode === "openpgp" ? "success" : "neutral"}
                      label={protectionLabel(receipt)}
                    />
                  </div>
                  <div className="font-mono mt-2 break-all text-primary">{receipt.receipt_code}</div>
                  <div className="mt-1 truncate text-secondary">From {receipt.sender}</div>
                  <div className="font-mono mt-1 truncate text-caption-md-regular text-tertiary">
                    Message-ID {receipt.message_id}
                  </div>
                  {receipt.key_fingerprint && (
                    <div className="font-mono mt-1 truncate text-caption-md-regular text-tertiary">
                      Encryption key {receipt.key_fingerprint}
                    </div>
                  )}
                </div>
                <div className="text-left text-secondary sm:text-right">
                  <div>{stateLabel(receipt)}</div>
                  <time dateTime={receipt.created_at}>{formatTimestamp(receipt.created_at)}</time>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
};
