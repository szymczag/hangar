import { useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, MailSearch, RotateCcw } from "lucide-react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { InstanceService } from "@plane/services";
import { Input } from "@plane/ui";

const instanceService = new InstanceService();

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
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Suppression removed", message: "Email delivery can resume." });
    } catch {
      setToast({ type: TOAST_TYPE.ERROR, title: "Review failed", message: "The suppression was not changed." });
    }
  };

  return (
    <section className="mt-12 border-t border-subtle pt-8" aria-labelledby="delivery-ledger-title">
      <div className="flex items-start gap-3">
        <div className="flex size-9 items-center justify-center rounded-md border border-subtle bg-layer-2">
          <MailSearch className="size-4 text-secondary" />
        </div>
        <div>
          <h2 id="delivery-ledger-title" className="text-16 font-medium text-primary">
            Email delivery ledger
          </h2>
          <p className="mt-1 max-w-3xl text-13 text-secondary">
            Operational receipts only. Message bodies, subjects, certificates, and SMTP credentials are never shown.
          </p>
        </div>
      </div>

      <div className="mt-5 grid max-w-4xl gap-3 sm:grid-cols-[1fr_1fr_auto]">
        <Input
          value={recipient}
          onChange={(event) => setRecipient(event.target.value)}
          placeholder="Exact recipient email"
        />
        <Input
          value={receipt}
          onChange={(event) => setReceipt(event.target.value.toUpperCase())}
          placeholder="Receipt code"
          className="font-mono uppercase"
        />
        <Button
          variant="secondary"
          onClick={() => setFilters({ recipient: recipient.trim(), receipt: receipt.trim() })}
        >
          Filter
        </Button>
      </div>

      <div className="mt-5 grid max-w-4xl grid-cols-2 gap-3 sm:grid-cols-4">
        {Object.entries(data?.status_counts ?? {}).map(([status, count]) => (
          <div key={status} className="rounded-md border border-subtle bg-layer-2 p-3">
            <div className="text-11 tracking-wide text-tertiary uppercase">{status.replaceAll("_", " ")}</div>
            <div className="mt-1 text-18 font-medium text-primary">{count}</div>
          </div>
        ))}
      </div>

      {(data?.oldest_due_age_seconds ?? 0) > 120 && (
        <div className="mt-4 flex max-w-4xl gap-2 rounded-md border border-warning-subtle bg-warning-subtle p-3 text-12 text-primary">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          The oldest due email has waited {Math.floor((data?.oldest_due_age_seconds ?? 0) / 60)} minutes. Check the
          dedicated mail worker, RabbitMQ, AWS identity, and SES quota before resetting any receipt.
        </div>
      )}

      <div className="mt-5 max-w-5xl overflow-x-auto rounded-md border border-subtle">
        <table className="w-full min-w-[860px] text-left text-12">
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
                  {new Date(row.created_at).toLocaleString()}
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
          <div className="flex gap-2 p-5 text-13 text-secondary">
            <Clock3 className="size-4" /> No matching receipts.
          </div>
        )}
      </div>

      {(suppressionData?.results.length ?? 0) > 0 && (
        <div className="mt-8 max-w-4xl rounded-md border border-warning-subtle bg-warning-subtle p-4">
          <div className="flex gap-2 text-13 font-medium text-primary">
            <AlertTriangle className="size-4" /> Active suppressions
          </div>
          <div className="mt-3 space-y-3">
            {suppressionData?.results.map((item) => (
              <div key={item.id} className="rounded-md border border-subtle bg-layer-1 p-3 text-12">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-medium text-primary">{item.recipient_email ?? "External recipient"}</span> ·{" "}
                    <span className="text-secondary">{item.reason.replaceAll("_", " ")}</span>
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => setReviewId(item.id)}>
                    <RotateCcw className="size-3.5" /> Review removal
                  </Button>
                </div>
                {reviewId === item.id && (
                  <div className="mt-3 flex gap-2">
                    <Input
                      value={reviewReason}
                      onChange={(event) => setReviewReason(event.target.value)}
                      placeholder="Document the verified correction or false positive"
                    />
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={reviewReason.trim().length < 10}
                      onClick={releaseSuppression}
                    >
                      <CheckCircle2 className="size-3.5" /> Confirm
                    </Button>
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
