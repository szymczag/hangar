/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */
import { useState } from "react";
import useSWR from "swr";
import { Button } from "@plane/propel/button";
import { CapacityService } from "@/services/capacity.service";
import { errorMessage } from "../shared/capacity-format.utils";

const service = new CapacityService();
/** Whether this rule can write, in words an administrator can act on. */
function WriterState({ status, email }: { status: string; email: string }) {
  if (status === "ok") {
    return <p className="text-11 text-secondary">Writes as {email || "a connected account"}</p>;
  }
  return (
    <p className="text-11 text-danger-primary">
      {status === "scope_missing"
        ? "The connected account has not granted permission to create events"
        : status === "reauthorization_required"
          ? "The connected account needs reconnecting"
          : "No account connected — workshops planned in Hangar are not written to this calendar"}
    </p>
  );
}

export function TrainingRules({
  workspaceSlug,
  onChanged,
}: {
  workspaceSlug: string;
  onChanged: () => Promise<unknown>;
}) {
  const {
    data,
    error: loadError,
    mutate,
  } = useSWR(["capacity-training-rules", workspaceSlug], () => service.listTrainingRules(workspaceSlug));
  const [rule, setRule] = useState({ label: "", calendar_id: "" });
  const [busy, setBusy] = useState(false);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState("");
  // Writing is a separate Google consent, taken by whoever keeps the training
  // calendar. It is deliberately not the trainer connection: that one reads, is
  // granted per trainer, and belongs to somebody else entirely.
  const connectWriter = async (ruleId: string) => {
    setBusy(true);
    setError("");
    try {
      const { authorization_url } = await service.startCalendarWriter(workspaceSlug, ruleId);
      // A separate flag from `busy`, because it is a separate fact: `busy` means
      // a request is in flight and always ends, while this means the page is on
      // its way to Google and is never cleared. Carrying both on one flag meant
      // a path where it never came back.
      setRedirecting(true);
      window.location.href = authorization_url;
    } catch (cause) {
      setError(errorMessage(cause, "Could not start the Google connection."));
    } finally {
      setBusy(false);
    }
  };

  const save = async (removeId?: string) => {
    setBusy(true);
    setError("");
    try {
      if (removeId) await service.deleteTrainingRule(workspaceSlug, removeId);
      else {
        await service.addTrainingRule(workspaceSlug, rule);
        setRule({ label: "", calendar_id: "" });
      }
      await mutate();
      await onChanged();
    } catch (cause) {
      setError(errorMessage(cause, "Could not save the training rule."));
    } finally {
      setBusy(false);
    }
  };
  return (
    <details className="rounded-xl border border-subtle bg-surface-1 p-5">
      <summary className="cursor-pointer text-body-sm-medium">
        Training calendar rules · Workspace administrators
      </summary>
      <p className="my-3 text-body-xs-regular text-secondary">
        Everything on this calendar counts as training. Whose training it is comes from each trainer&apos;s own copy of
        the invitation, so a trainer who has not granted event access appears here as having none. Rules apply to this
        workspace, and the calendar identifier is encrypted in storage.
      </p>
      {(error || loadError) && (
        <p role="alert" className="text-body-xs-regular text-danger-primary">
          {error || "Could not load training rules."}
        </p>
      )}
      <ul className="space-y-3">
        {data?.results.map((item) => (
          <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-subtle py-2">
            <div>
              <strong className="text-body-xs-medium">{item.label}</strong>
              <p className="text-body-xs-regular break-all text-secondary">{item.calendar_id}</p>
              <WriterState status={item.writer_status} email={item.writer_email} />
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant={item.writer_status === "ok" ? "secondary" : "primary"}
                disabled={busy || redirecting}
                onClick={() => void connectWriter(item.id)}
              >
                {item.writer_status === "ok" ? "Change writing account" : "Connect writing account"}
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => void save(item.id)}>
                Remove rule
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <form
        className="mt-4 grid gap-3 md:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        {(
          [
            { key: "label", label: "Rule name" },
            { key: "calendar_id", label: "Calendar ID" },
          ] as const
        ).map((field) => (
          <label key={field.key} className="text-body-xs-medium">
            {field.label}
            <input
              required
              type="text"
              autoComplete="off"
              value={rule[field.key]}
              disabled={busy}
              onChange={(event) => setRule({ ...rule, [field.key]: event.target.value })}
              className="mt-1 w-full rounded border border-subtle bg-surface-2 p-2 text-body-xs-regular"
            />
          </label>
        ))}
        <Button type="submit" variant="primary" size="sm" disabled={busy || !data}>
          Add rule
        </Button>
      </form>
    </details>
  );
}
