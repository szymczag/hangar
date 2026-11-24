/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useReducer, useState } from "react";
import useSWR from "swr";
import type { IEmailSecurityStatus, IOpenPGPEmailKey } from "@plane/types";
import { Banner } from "@makeplane/propel/components/banner";
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { InputField } from "@makeplane/propel/components/input-field";
import { TextAreaField } from "@makeplane/propel/components/text-area-field";
import { DeleteOutline, KeyOutline, MailCheckOutline, TickOutline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { cn } from "@plane/utils";
// components
import { SettingsHeading } from "@/components/settings/heading";
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
  <dl className="grid gap-3 rounded-lg border border-subtle bg-layer-1 p-4 text-body-xs-regular sm:grid-cols-2">
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
            {step.complete ? <TickOutline className="size-3.5" /> : index + 1}
          </span>
          <span className={cn("truncate text-caption-md-regular", step.complete ? "text-primary" : "text-secondary")}>
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
};

/** The OpenPGP certificate field: monospace, never spell-checked or autofilled. */
const CertificateField = ({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) => (
  <div className="[&_textarea]:font-mono">
    <TextAreaField
      size="lg"
      resize="vertical"
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder="-----BEGIN PGP PUBLIC KEY BLOCK-----"
      rows={8}
      spellCheck={false}
      autoComplete="off"
    />
  </div>
);

/** The current password a key change asks for, when the account has one (S9). */
const CurrentPasswordField = ({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) => (
  <InputField
    size="lg"
    orientation="vertical"
    type="password"
    aria-label={label}
    placeholder={label}
    value={value}
    onChange={(event) => onChange(event.target.value)}
    autoComplete="current-password"
  />
);

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
      setToast({ type: "success", title: "Email security updated", message: success });
    } catch (error) {
      setToast({ type: "error", title: "Email security update failed", message: errorMessage(error) });
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
    return <div className="mt-10 h-48 animate-pulse rounded-lg bg-layer-1" aria-label="Loading email security" />;
  }

  const passwordRequired = !currentUser?.is_password_autoset;

  return (
    <section className="mt-12 border-t border-subtle pt-8" aria-labelledby="email-security-title">
      <SettingsHeading
        variant="h4"
        title={<span id="email-security-title">Encrypted email notifications</span>}
        description="Verify an OpenPGP public key to receive project activity and export emails. Account access and recovery messages remain unencrypted so you cannot be locked out."
      />

      {!data.enabled && (
        <div className="mt-6 max-w-3xl">
          <Banner
            variant="warning"
            placement="inline"
            description="Encrypted notifications are not switched on for this instance yet. You can add and verify your key now — it starts being used the moment an administrator enables them, with nothing further to do."
          />
        </div>
      )}

      <div className="mt-7 flex max-w-3xl flex-col gap-7">
        <Lifecycle status={data} />

        {data.active_key && !data.pending_key ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-body-xs-medium text-success-primary">
              <Icon icon={MailCheckOutline} /> Notifications are encrypted
            </div>
            <KeySummary value={data.active_key} />
            {showReplacement && (
              <CertificateField label="Replacement public certificate" value={certificate} onChange={setCertificate} />
            )}
            {passwordRequired && (
              <CurrentPasswordField
                label={
                  showReplacement
                    ? "Current password required to replace this key"
                    : "Current password required to remove this key"
                }
                value={password}
                onChange={setPassword}
              />
            )}
            <div className="flex flex-wrap gap-2">
              {showReplacement ? (
                <Button
                  variant="primary"
                  size="lg"
                  stretch="auto"
                  label="Upload replacement"
                  loading={busyAction === "upload"}
                  disabled={!certificate.trim() || (passwordRequired && !password)}
                  onClick={() => void upload()}
                />
              ) : (
                <Button
                  variant="secondary"
                  size="lg"
                  stretch="auto"
                  label="Replace public key"
                  onClick={() => setShowReplacement(true)}
                />
              )}
              <Button
                variant="secondary"
                size="lg"
                stretch="auto"
                label="Send encrypted test"
                loading={busyAction === "test"}
                onClick={() =>
                  void run(
                    "test",
                    () => userService.sendOpenPGPTest(data.active_key!.id),
                    "An encrypted test message was queued."
                  )
                }
              />
              <Button
                variant="danger-outline"
                size="lg"
                stretch="auto"
                icon={<Icon icon={DeleteOutline} />}
                label={confirmRemoval === data.active_key.id ? "Confirm removal" : "Remove key"}
                loading={busyAction === "remove"}
                disabled={passwordRequired && !password}
                onClick={() =>
                  confirmRemoval === data.active_key!.id
                    ? void remove(data.active_key!.id)
                    : setConfirmRemoval(data.active_key!.id)
                }
              />
            </div>
          </div>
        ) : data.pending_key ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-body-xs-medium text-primary">
              <Icon icon={KeyOutline} /> Verification required
            </div>
            {data.active_key && (
              <p className="text-body-xs-regular text-secondary">
                Your existing active key remains in use until this replacement is verified.
              </p>
            )}
            <KeySummary value={data.pending_key} />
            <p className="text-body-xs-regular text-secondary">
              Send a challenge, decrypt it with your private key, then enter the code below. Hangar never receives or
              stores your private key.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="lg"
                stretch="auto"
                label="Send encrypted challenge"
                loading={busyAction === "challenge"}
                onClick={() =>
                  void run(
                    "challenge",
                    () => userService.sendOpenPGPChallenge(data.pending_key!.id),
                    "The encrypted verification message was queued."
                  )
                }
              />
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
              <div className="[&_input]:font-mono flex-1 [&_input]:uppercase">
                <InputField
                  size="lg"
                  orientation="vertical"
                  aria-label="Verification code"
                  placeholder="Verification code"
                  value={code}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  autoComplete="one-time-code"
                />
              </div>
              <Button
                variant="primary"
                size="lg"
                stretch="auto"
                label="Verify key"
                disabled={code.trim().length < 8}
                loading={busyAction === "verify"}
                onClick={() =>
                  void run(
                    "verify",
                    async () => {
                      await userService.verifyOpenPGPChallenge(data.pending_key!.id, code.trim());
                      setCode("");
                    },
                    "The key is verified. Future project notifications will be encrypted."
                  )
                }
              />
            </div>
            {passwordRequired && (
              <CurrentPasswordField
                label="Current password required to discard this key"
                value={password}
                onChange={setPassword}
              />
            )}
            <div>
              <Button
                variant="danger-outline"
                size="lg"
                stretch="auto"
                label={confirmRemoval === data.pending_key.id ? "Confirm discard" : "Discard pending key"}
                loading={busyAction === "remove"}
                disabled={passwordRequired && !password}
                onClick={() =>
                  confirmRemoval === data.pending_key!.id
                    ? void remove(data.pending_key!.id)
                    : setConfirmRemoval(data.pending_key!.id)
                }
              />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <Banner
              variant="neutral"
              placement="inline"
              icon={null}
              description="Project and export emails are currently silenced. Paste one ASCII-armored public certificate below; private keys and private-key blocks are rejected."
            />
            <CertificateField label="OpenPGP public certificate" value={certificate} onChange={setCertificate} />
            {passwordRequired && (
              <CurrentPasswordField label="Current password" value={password} onChange={setPassword} />
            )}
            <div>
              <Button
                variant="primary"
                size="lg"
                stretch="auto"
                label="Upload public key"
                disabled={!certificate.trim() || (passwordRequired && !password)}
                loading={busyAction === "upload"}
                onClick={() => void upload()}
              />
            </div>
          </div>
        )}
      </div>
      {data.active_suppressions.length > 0 && (
        <div className="mt-6 max-w-3xl">
          <Banner
            variant="danger"
            placement="inline"
            description="Email delivery to your address is paused after a provider complaint or permanent bounce. Correct the address if needed, then contact an instance administrator for a reviewed reactivation."
          />
        </div>
      )}
      <EmailReceiptLedger />
    </section>
  );
};
