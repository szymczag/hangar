/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { CheckCircle2, MailWarning, Search, ShieldCheck } from "lucide-react";
import useSWR from "swr";
import type { IEmailReceipt } from "@plane/types";
import { Button } from "@plane/propel/button";
import { Input } from "@plane/ui";
import { cn } from "@plane/utils";
import { UserService } from "@/services/user.service";

const userService = new UserService();

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
    <section className="mt-10 border-t border-subtle-1 pt-8" aria-labelledby="email-receipts-title">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-subtle-1 bg-layer-2">
          <ShieldCheck className="size-4 text-secondary" />
        </div>
        <div>
          <h2 id="email-receipts-title" className="text-16 font-medium text-primary">
            Verify a Hangar email
          </h2>
          <p className="mt-1 max-w-2xl text-13 leading-5 text-secondary">
            Every legitimate message contains a Hangar email receipt. Match that code here before following an
            unexpected link or opening an attachment. This ledger never stores the email body.
          </p>
        </div>
      </div>

      <div className="mt-5 flex max-w-xl gap-2">
        <Input
          aria-label="Hangar email receipt"
          value={query}
          onChange={(event) => setQuery(event.target.value.toUpperCase())}
          onKeyDown={(event) => event.key === "Enter" && verify()}
          placeholder="ABCD-EF12-3456-7890-ABCD"
          className="font-mono uppercase"
        />
        <Button variant="secondary" onClick={verify} disabled={!query.trim()}>
          <Search className="size-4" /> Verify
        </Button>
      </div>

      <div className="mt-5 max-w-3xl overflow-hidden rounded-md border border-subtle-1">
        {isLoading ? (
          <div className="h-28 animate-pulse bg-layer-2" aria-label="Loading email receipts" />
        ) : rows.length === 0 ? (
          <div className="flex gap-3 p-5 text-13 text-secondary">
            <MailWarning className="mt-0.5 size-4 shrink-0" />
            <p>
              {appliedQuery
                ? "No Hangar email matches this receipt. Treat the message as suspicious."
                : "No email receipts are available yet."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-subtle-1">
            {rows.map((receipt) => (
              <li key={receipt.receipt_code} className="grid gap-3 p-4 text-12 sm:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 shrink-0 text-success-primary" />
                    <span className="font-medium text-primary">{receipt.mail_type}</span>
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-11",
                        receipt.delivery_mode === "openpgp"
                          ? "bg-success-subtle text-success-primary"
                          : "bg-layer-2 text-secondary"
                      )}
                    >
                      {protectionLabel(receipt)}
                    </span>
                  </div>
                  <div className="font-mono mt-2 break-all text-primary">{receipt.receipt_code}</div>
                  <div className="mt-1 truncate text-secondary">From {receipt.sender}</div>
                  <div className="font-mono mt-1 truncate text-11 text-tertiary">Message-ID {receipt.message_id}</div>
                  {receipt.key_fingerprint && (
                    <div className="font-mono mt-1 truncate text-11 text-tertiary">
                      Encryption key {receipt.key_fingerprint}
                    </div>
                  )}
                </div>
                <div className="text-left text-secondary sm:text-right">
                  <div>{stateLabel(receipt)}</div>
                  <time dateTime={receipt.created_at}>{new Date(receipt.created_at).toLocaleString()}</time>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
};
