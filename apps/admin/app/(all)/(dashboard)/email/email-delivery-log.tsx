/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { InputField } from "@makeplane/propel/components/input-field";
import {
  ClockOutline,
  MailCheckOutline,
  RestoreOutline,
  TickCircleOutline,
  WarningTriangleOutline,
} from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { InstanceService } from "@plane/services";

const instanceService = new InstanceService();
const TIMESTAMP_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : `${TIMESTAMP_FORMATTER.format(date)} UTC`;
};

export const EmailDeliveryLog = () => {
  const [recipient, setRecipient] = useState("");
  const [receipt, setReceipt] = useState("");
  const [filters, setFilters] = useState({ recipient: "", receipt: "" });
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const { data, isLoading } = useSWR(["INSTANCE_EMAIL_DELIVERY_LOG", filters], () =>
    instanceService.emailDeliveryLog({ ...filters, limit: 100 })
  );
  const { data: suppressionData, mutate: mutateSuppressions } = useSWR("INSTANCE_EMAIL_SUPPRESSIONS", () =>
    instanceService.emailSuppressions()
  );

  const releaseSuppression = async () => {
    if (!reviewId || reviewReason.trim().length < 10) return;
    try {
      await instanceService.deactivateEmailSuppression(reviewId, reviewReason.trim());
      await mutateSuppressions();
      setReviewId(null);
      setReviewReason("");
      setToast({ type: "success", title: "Suppression removed", message: "Email delivery can resume." });
    } catch {
      setToast({ type: "error", title: "Review failed", message: "The suppression was not changed." });
    }
  };

  return (
    <section className="mt-12 border-t border-subtle pt-8" aria-labelledby="delivery-ledger-title">
      <div className="flex items-start gap-3">
        <div className="flex size-9 items-center justify-center rounded-md border border-subtle bg-layer-2">
          <MailCheckOutline className="size-4 text-secondary" />
        </div>
        <div>
          <h2 id="delivery-ledger-title" className="text-body-md-medium text-primary">
            Email delivery ledger
          </h2>
          <p className="mt-1 max-w-3xl text-body-xs-regular text-secondary">
            Operational receipts only. Message bodies, subjects, certificates, and SMTP credentials are never shown.
          </p>
        </div>
      </div>

      <div className="mt-5 grid max-w-4xl items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
        <InputField
          size="md"
          orientation="vertical"
          label="Recipient"
          value={recipient}
          onChange={(event) => setRecipient(event.target.value)}
          placeholder="Exact recipient email"
        />
        <InputField
          size="md"
          orientation="vertical"
          label="Receipt code"
          value={receipt}
          onChange={(event) => setReceipt(event.target.value.toUpperCase())}
          placeholder="Receipt code"
        />
        <Button
          variant="secondary"
          size="md"
          stretch="auto"
          onClick={() => setFilters({ recipient: recipient.trim(), receipt: receipt.trim() })}
          label="Filter"
        />
      </div>

      <div className="mt-5 grid max-w-4xl grid-cols-2 gap-3 sm:grid-cols-4">
        {Object.entries(data?.status_counts ?? {}).map(([status, count]) => (
          <div key={status} className="rounded-md border border-subtle bg-layer-2 p-3">
            <div className="text-caption-sm-medium tracking-wide text-tertiary uppercase">
              {status.replaceAll("_", " ")}
            </div>
            <div className="mt-1 text-h5-medium text-primary">{count}</div>
          </div>
        ))}
      </div>

      {(data?.oldest_due_age_seconds ?? 0) > 120 && (
        <div className="mt-4 flex max-w-4xl gap-2 rounded-md border border-warning-subtle bg-warning-subtle p-3 text-body-xs-regular text-primary">
          <WarningTriangleOutline className="mt-0.5 size-4 shrink-0" />
          The oldest due email has waited {Math.floor((data?.oldest_due_age_seconds ?? 0) / 60)} minutes. Check the
          dedicated mail worker, RabbitMQ, AWS identity, and SES quota before resetting any receipt.
        </div>
      )}

      <div className="mt-5 max-w-5xl overflow-x-auto rounded-md border border-subtle">
        <table className="w-full min-w-[860px] text-left text-body-xs-regular">
          <thead className="bg-layer-2 text-tertiary">
            <tr>
              <th className="px-3 py-2 font-medium">Created</th>
              <th className="px-3 py-2 font-medium">Receipt</th>
              <th className="px-3 py-2 font-medium">Message type</th>
              <th className="px-3 py-2 font-medium">Recipient</th>
              <th className="px-3 py-2 font-medium">Protection</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Attempts</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-subtle">
            {(data?.results ?? []).map((row) => (
              <tr key={row.receipt_code}>
                <td className="px-3 py-3 whitespace-nowrap text-secondary">
                  <time dateTime={row.created_at}>{formatTimestamp(row.created_at)}</time>
                </td>
                <td className="font-mono px-3 py-3 text-primary">{row.receipt_code}</td>
                <td className="px-3 py-3 text-primary">{row.mail_type}</td>
                <td className="px-3 py-3 text-secondary">{row.recipient_email ?? "Unavailable"}</td>
                <td className="px-3 py-3 text-secondary">{row.delivery_mode}</td>
                <td className="px-3 py-3 text-secondary">{row.status.replaceAll("_", " ")}</td>
                <td className="px-3 py-3 text-secondary">{row.attempts ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && (data?.results.length ?? 0) === 0 && (
          <div className="flex gap-2 p-5 text-body-xs-regular text-secondary">
            <ClockOutline className="size-4" /> No matching receipts.
          </div>
        )}
      </div>

      {(suppressionData?.results.length ?? 0) > 0 && (
        <div className="mt-8 max-w-4xl rounded-md border border-warning-subtle bg-warning-subtle p-4">
          <div className="flex gap-2 text-body-xs-medium text-primary">
            <WarningTriangleOutline className="size-4" /> Active suppressions
          </div>
          <div className="mt-3 space-y-3">
            {suppressionData?.results.map((item) => (
              <div key={item.id} className="rounded-md border border-subtle bg-layer-1 p-3 text-body-xs-regular">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-medium text-primary">{item.recipient_email ?? "External recipient"}</span> ·{" "}
                    <span className="text-secondary">{item.reason.replaceAll("_", " ")}</span>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    stretch="auto"
                    icon={<Icon icon={RestoreOutline} />}
                    onClick={() => setReviewId(item.id)}
                    label="Review removal"
                  />
                </div>
                {reviewId === item.id && (
                  <div className="mt-3 flex items-end gap-2">
                    <div className="min-w-0 flex-1">
                      <InputField
                        size="md"
                        orientation="vertical"
                        label="Reason for removal"
                        value={reviewReason}
                        onChange={(event) => setReviewReason(event.target.value)}
                        placeholder="Document the verified correction or false positive"
                      />
                    </div>
                    <Button
                      variant="primary"
                      size="md"
                      stretch="auto"
                      icon={<Icon icon={TickCircleOutline} />}
                      disabled={reviewReason.trim().length < 10}
                      onClick={() => void releaseSuppression()}
                      label="Confirm"
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
};
