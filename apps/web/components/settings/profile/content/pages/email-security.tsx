/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useReducer, useState } from "react";
import { Check, KeyRound, LockKeyhole, MailCheck, ShieldAlert, Trash2 } from "lucide-react";
import useSWR from "swr";
import type { IEmailSecurityStatus, IOpenPGPEmailKey } from "@plane/types";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Input, TextArea } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useUser } from "@/hooks/store/user";
// services
import { UserService } from "@/services/user.service";
import { EmailReceiptLedger } from "./email-receipts";

const userService = new UserService();
const STATUS_KEY = "CURRENT_USER_EMAIL_SECURITY";
const DATE_FORMATTER = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeZone: "UTC" });
const TIMESTAMP_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

const formatDate = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : `${DATE_FORMATTER.format(date)} UTC`;
};

const formatTimestamp = (value: string): string => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : `${TIMESTAMP_FORMATTER.format(date)} UTC`;
};

const busyActionReducer = (_current: string | null, next: string | null): string | null => next;

const errorMessage = (error: unknown): string => {
  if (error && typeof error === "object" && "error" in error && typeof error.error === "string") {
    return error.error;
  }
  return "The email security change could not be completed.";
};

const formatFingerprint = (fingerprint: string) => fingerprint.match(/.{1,4}/g)?.join(" ") ?? fingerprint;

const KeySummary = ({ value }: { value: IOpenPGPEmailKey }) => (
  <dl className="grid gap-3 rounded-md border border-subtle-1 bg-layer-2 p-4 text-12 sm:grid-cols-2">
    <div className="sm:col-span-2">
      <dt className="text-secondary">Primary fingerprint</dt>
      <dd className="font-mono mt-1 break-all text-primary">{formatFingerprint(value.primary_fingerprint)}</dd>
    </div>
    <div className="sm:col-span-2">
      <dt className="text-secondary">Selected encryption key</dt>
      <dd className="font-mono mt-1 break-all text-primary">
        {formatFingerprint(value.encryption_subkey_fingerprint)}
      </dd>
    </div>
    <div>
      <dt className="text-secondary">Encryption key</dt>
      <dd className="mt-1 text-primary">
        {value.encryption_algorithm}
        {value.encryption_key_size ? ` · ${value.encryption_key_size} bit` : ""}
      </dd>
    </div>
    <div>
      <dt className="text-secondary">Created</dt>
      <dd className="mt-1 text-primary">{value.key_created_at ? formatDate(value.key_created_at) : "Unknown"}</dd>
    </div>
    <div>
      <dt className="text-secondary">Expires</dt>
      <dd className="mt-1 text-primary">{value.key_expires_at ? formatDate(value.key_expires_at) : "No expiry"}</dd>
    </div>
    {value.verified_at && (
      <div>
        <dt className="text-secondary">Verified</dt>
        <dd className="mt-1 text-primary">{formatTimestamp(value.verified_at)}</dd>
      </div>
    )}
  </dl>
);

const Lifecycle = ({ status }: { status: IEmailSecurityStatus }) => {
  const steps = [
    { label: "Uploaded", complete: Boolean(status.pending_key || status.active_key) },
    { label: "Verified", complete: Boolean(status.active_key) },
    { label: "Encrypted notifications", complete: status.notification_mode === "encrypted" },
  ];

  return (
    <ol className="grid grid-cols-3 gap-2" aria-label="OpenPGP key setup progress">
      {steps.map((step, index) => (
        <li key={step.label} className="relative flex min-w-0 flex-col items-center gap-2 text-center">
          {index > 0 && <span className="bg-border-subtle-1 absolute top-3 right-1/2 h-px w-full" aria-hidden="true" />}
          <span
            className={cn(
              "relative z-[1] flex size-6 items-center justify-center rounded-full border bg-layer-1",
              step.complete ? "border-success-strong text-success-primary" : "border-subtle-1 text-placeholder"
            )}
          >
            {step.complete ? <Check className="size-3.5" /> : index + 1}
          </span>
          <span className={cn("truncate text-11", step.complete ? "text-primary" : "text-secondary")}>
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
};

export const EmailSecuritySettings = () => {
  const { data: currentUser } = useUser();
  const { data, mutate, isLoading } = useSWR(STATUS_KEY, () => userService.getEmailSecurityStatus());
  const [certificate, setCertificate] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [showReplacement, setShowReplacement] = useState(false);
  const [busyAction, dispatchBusyAction] = useReducer(busyActionReducer, null);
  const [confirmRemoval, setConfirmRemoval] = useState<string | null>(null);

  const run = async (action: string, operation: () => Promise<unknown>, success: string) => {
    dispatchBusyAction(action);
    try {
      await operation();
      await mutate();
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Email security updated", message: success });
    } catch (error) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Email security update failed", message: errorMessage(error) });
    } finally {
      dispatchBusyAction(null);
    }
  };

  const upload = () =>
    run(
      "upload",
      async () => {
        await userService.uploadOpenPGPKey(certificate, password || undefined);
        setCertificate("");
        setPassword("");
        setShowReplacement(false);
      },
      "The public key was accepted. Send the encrypted challenge to verify ownership."
    );

  const remove = (keyId: string) =>
    run(
      "remove",
      async () => {
        await userService.removeOpenPGPKey(keyId, password || undefined);
        setPassword("");
        setCode("");
        setConfirmRemoval(null);
      },
      "The selected key was removed and the notification policy was updated."
    );

  if (isLoading || !data) {
    return <div className="mt-10 h-48 animate-pulse rounded-md bg-layer-2" aria-label="Loading email security" />;
  }

  return (
    <section className="mt-12 border-t border-subtle-1 pt-8" aria-labelledby="email-security-title">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-subtle-1 bg-layer-2">
          <LockKeyhole className="size-4 text-secondary" />
        </div>
        <div>
          <h2 id="email-security-title" className="text-16 font-medium text-primary">
            Encrypted email notifications
          </h2>
          <p className="mt-1 max-w-2xl text-13 leading-5 text-secondary">
            Verify an OpenPGP public key to receive project activity and export emails. Account access and recovery
            messages remain unencrypted so you cannot be locked out.
          </p>
        </div>
      </div>

      {!data.enabled && (
        <div className="mt-6 flex gap-3 rounded-md border border-warning-subtle bg-warning-subtle p-4 text-13">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <p>
            Encrypted notifications are not switched on for this instance yet. You can add and verify your key now — it
            starts being used the moment an administrator enables them, with nothing further to do.
          </p>
        </div>
      )}

      <div className="mt-7 flex max-w-3xl flex-col gap-7">
        <Lifecycle status={data} />

        {data.active_key && !data.pending_key ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-13 font-medium text-success-primary">
              <MailCheck className="size-4" /> Notifications are encrypted
            </div>
            <KeySummary value={data.active_key} />
            {showReplacement && (
              <label htmlFor="replacement-openpgp-certificate" className="flex flex-col gap-2 text-13 text-primary">
                Replacement public certificate
                <TextArea
                  id="replacement-openpgp-certificate"
                  value={certificate}
                  onChange={(event) => setCertificate(event.target.value)}
                  placeholder="-----BEGIN PGP PUBLIC KEY BLOCK-----"
                  rows={8}
                  className="font-mono min-h-40 text-11"
                  spellCheck={false}
                  autoComplete="off"
                />
              </label>
            )}
            {!currentUser?.is_password_autoset && (
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={
                  showReplacement
                    ? "Current password required to replace this key"
                    : "Current password required to remove this key"
                }
                autoComplete="current-password"
              />
            )}
            <div className="flex flex-wrap gap-2">
              {showReplacement ? (
                <Button
                  variant="primary"
                  size="lg"
                  loading={busyAction === "upload"}
                  disabled={!certificate.trim() || (!currentUser?.is_password_autoset && !password)}
                  onClick={upload}
                >
                  Upload replacement
                </Button>
              ) : (
                <Button variant="secondary" size="lg" onClick={() => setShowReplacement(true)}>
                  Replace public key
                </Button>
              )}
              <Button
                variant="secondary"
                size="lg"
                loading={busyAction === "test"}
                onClick={() =>
                  run(
                    "test",
                    () => userService.sendOpenPGPTest(data.active_key!.id),
                    "An encrypted test message was queued."
                  )
                }
              >
                Send encrypted test
              </Button>
              <Button
                variant="error-outline"
                size="lg"
                loading={busyAction === "remove"}
                disabled={!currentUser?.is_password_autoset && !password}
                onClick={() =>
                  confirmRemoval === data.active_key!.id
                    ? remove(data.active_key!.id)
                    : setConfirmRemoval(data.active_key!.id)
                }
              >
                <Trash2 className="size-4" />
                {confirmRemoval === data.active_key.id ? "Confirm removal" : "Remove key"}
              </Button>
            </div>
          </div>
        ) : data.pending_key ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-13 font-medium text-primary">
              <KeyRound className="size-4" /> Verification required
            </div>
            {data.active_key && (
              <p className="text-12 leading-5 text-secondary">
                Your existing active key remains in use until this replacement is verified.
              </p>
            )}
            <KeySummary value={data.pending_key} />
            <p className="text-12 leading-5 text-secondary">
              Send a challenge, decrypt it with your private key, then enter the code below. Hangar never receives or
              stores your private key.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="lg"
                loading={busyAction === "challenge"}
                onClick={() =>
                  run(
                    "challenge",
                    () => userService.sendOpenPGPChallenge(data.pending_key!.id),
                    "The encrypted verification message was queued."
                  )
                }
              >
                Send encrypted challenge
              </Button>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder="Verification code"
                autoComplete="one-time-code"
                className="font-mono uppercase"
              />
              <Button
                variant="primary"
                size="lg"
                disabled={code.trim().length < 8}
                loading={busyAction === "verify"}
                onClick={() =>
                  run(
                    "verify",
                    async () => {
                      await userService.verifyOpenPGPChallenge(data.pending_key!.id, code.trim());
                      setCode("");
                    },
                    "The key is verified. Future project notifications will be encrypted."
                  )
                }
              >
                Verify key
              </Button>
            </div>
            {!currentUser?.is_password_autoset && (
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Current password required to discard this key"
                autoComplete="current-password"
              />
            )}
            <Button
              variant="error-outline"
              size="lg"
              className="self-start"
              loading={busyAction === "remove"}
              disabled={!currentUser?.is_password_autoset && !password}
              onClick={() =>
                confirmRemoval === data.pending_key!.id
                  ? remove(data.pending_key!.id)
                  : setConfirmRemoval(data.pending_key!.id)
              }
            >
              {confirmRemoval === data.pending_key.id ? "Confirm discard" : "Discard pending key"}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="rounded-md border border-subtle-1 bg-layer-2 p-4 text-13 leading-5 text-secondary">
              Project and export emails are currently silenced. Paste one ASCII-armored public certificate below;
              private keys and private-key blocks are rejected.
            </div>
            <label htmlFor="openpgp-certificate" className="flex flex-col gap-2 text-13 text-primary">
              OpenPGP public certificate
              <TextArea
                id="openpgp-certificate"
                value={certificate}
                onChange={(event) => setCertificate(event.target.value)}
                placeholder="-----BEGIN PGP PUBLIC KEY BLOCK-----"
                rows={8}
                className="font-mono min-h-40 text-11"
                spellCheck={false}
                autoComplete="off"
              />
            </label>
            {!currentUser?.is_password_autoset && (
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Current password"
                autoComplete="current-password"
              />
            )}
            <Button
              variant="primary"
              size="lg"
              className="self-start"
              disabled={!certificate.trim() || (!currentUser?.is_password_autoset && !password)}
              loading={busyAction === "upload"}
              onClick={upload}
            >
              Upload public key
            </Button>
          </div>
        )}
      </div>
      {data.active_suppressions.length > 0 && (
        <div className="mt-6 flex max-w-3xl gap-3 rounded-md border border-danger-subtle bg-danger-subtle p-4 text-13">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          <p>
            Email delivery to your address is paused after a provider complaint or permanent bounce. Correct the address
            if needed, then contact an instance administrator for a reviewed reactivation.
          </p>
        </div>
      )}
      <EmailReceiptLedger />
    </section>
  );
};
