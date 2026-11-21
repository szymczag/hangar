/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
// plane internal packages
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { InputField } from "@makeplane/propel/components/input-field";
import { TextAreaField } from "@makeplane/propel/components/text-area-field";
import { TextButton } from "@makeplane/propel/components/text-button";
import { KeyOutline, LockOutline, UnlockedOutline } from "@makeplane/propel/icons";
import { setToast } from "@plane/blocks/toast";
import { AuthService, InstanceOpenPGPService } from "@plane/services";
import type { TUserOpenPGPState } from "@plane/services";
// helpers
import { configurationErrorMessage } from "@/helpers/configuration-error";

const authService = new AuthService();
const openPGPService = new InstanceOpenPGPService();

type Props = {
  userId: string;
  email: string;
};

/**
 * Set or freeze the certificate this account's mail is encrypted to.
 *
 * Worth being blunt in the interface as well as the code: a key set here is
 * trusted without the challenge that normally proves the account holder controls
 * the private half. An administrator who sets a key they hold can read that
 * person's mail, which is the point when keys are escrowed and a problem when it
 * is not understood. The server records every action and emails the owner.
 */
export function OpenPGPControl(props: Props) {
  const { userId, email } = props;
  // states
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);
  const [state, setState] = useState<TUserOpenPGPState | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [certificate, setCertificate] = useState("");
  const [note, setNote] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
    openPGPService
      .state(userId)
      .then(setState)
      .catch(() => setState(null));
  }, [isOpen, userId]);

  const report = (error: unknown, title: string) =>
    setToast({
      type: "error",
      title,
      message: configurationErrorMessage(error, "The change was not applied."),
    });

  const applyKey = async () => {
    if (!csrfToken || !certificate.trim()) return;
    setIsBusy(true);
    try {
      setState(await openPGPService.setKey(csrfToken, userId, { certificate, note }));
      setCertificate("");
      setToast({
        type: "success",
        title: "Key set",
        message: `${email} has been notified that an administrator set their encryption key.`,
      });
    } catch (error) {
      report(error, "Key not set");
    } finally {
      setIsBusy(false);
    }
  };

  const toggleLock = async () => {
    if (!csrfToken || !state) return;
    setIsBusy(true);
    try {
      setState(await openPGPService.setLock(csrfToken, userId, { is_locked: !state.is_locked, note }));
    } catch (error) {
      report(error, "Lock not changed");
    } finally {
      setIsBusy(false);
    }
  };

  if (!isOpen) {
    return <TextButton variant="secondary" size="md" onClick={() => setIsOpen(true)} label="Manage key" />;
  }

  return (
    <div className="mt-2 flex max-w-xl flex-col gap-3 rounded-lg border border-subtle bg-layer-1 p-3">
      <div className="flex items-center gap-2 text-caption-md-regular text-tertiary">
        <KeyOutline className="size-3.5" />
        {state?.active_key ? (
          <span className="font-mono">{state.active_key.primary_fingerprint}</span>
        ) : (
          <span>No active key</span>
        )}
        {state?.is_locked && (
          <span className="flex items-center gap-1 text-warning-primary">
            <LockOutline className="size-3.5" /> self-service locked
          </span>
        )}
      </div>

      <TextAreaField
        size="lg"
        label="Public key"
        placeholder="-----BEGIN PGP PUBLIC KEY BLOCK-----"
        value={certificate}
        onChange={(event) => setCertificate(event.target.value)}
      />
      <InputField
        size="md"
        orientation="vertical"
        label="Reason"
        placeholder="Why (recorded, and not editable afterwards)"
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <p className="text-caption-md-regular text-tertiary">
        A key set here is activated without the email challenge that normally proves the account holder controls the
        private key — you are vouching for it instead. Whoever holds that private key can read {email}&apos;s
        notifications. The action is recorded permanently and {email} is emailed.
      </p>

      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          stretch="auto"
          onClick={() => void applyKey()}
          disabled={!certificate.trim() || isBusy}
          label="Set key"
        />
        <Button
          variant="secondary"
          size="sm"
          stretch="auto"
          onClick={() => void toggleLock()}
          disabled={isBusy || !state}
          icon={<Icon icon={state?.is_locked ? UnlockedOutline : LockOutline} />}
          label={state?.is_locked ? "Allow self-service" : "Lock self-service"}
        />
        <TextButton variant="secondary" size="md" onClick={() => setIsOpen(false)} label="Close" />
      </div>
    </div>
  );
}
