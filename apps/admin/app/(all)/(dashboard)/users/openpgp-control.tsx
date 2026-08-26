/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { KeyRound, Lock, LockOpen } from "lucide-react";
// plane internal packages
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
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
      type: TOAST_TYPE.ERROR,
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
        type: TOAST_TYPE.SUCCESS,
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
    return (
      <button type="button" className="text-11 text-tertiary underline" onClick={() => setIsOpen(true)}>
        Manage key
      </button>
    );
  }

  return (
    <div className="mt-2 flex max-w-xl flex-col gap-3 rounded-md border border-strong p-3">
      <div className="flex items-center gap-2 text-11 text-tertiary">
        <KeyRound className="size-3.5" />
        {state?.active_key ? (
          <span className="font-mono">{state.active_key.primary_fingerprint}</span>
        ) : (
          <span>No active key</span>
        )}
        {state?.is_locked && (
          <span className="flex items-center gap-1 text-warning-primary">
            <Lock className="size-3.5" /> self-service locked
          </span>
        )}
      </div>

      <textarea
        className="font-mono h-24 w-full rounded-md border border-strong bg-surface-1 p-2 text-11"
        placeholder="-----BEGIN PGP PUBLIC KEY BLOCK-----"
        value={certificate}
        onChange={(event) => setCertificate(event.target.value)}
      />
      <input
        className="w-full rounded-md border border-strong bg-surface-1 px-2 py-1 text-11"
        placeholder="Why (recorded, and not editable afterwards)"
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <p className="text-11 text-tertiary">
        A key set here is activated without the email challenge that normally proves the account holder controls the
        private key — you are vouching for it instead. Whoever holds that private key can read {email}&apos;s
        notifications. The action is recorded permanently and {email} is emailed.
      </p>

      <div className="flex items-center gap-2">
        <Button variant="primary" size="sm" onClick={applyKey} disabled={!certificate.trim() || isBusy}>
          Set key
        </Button>
        <Button variant="secondary" size="sm" onClick={toggleLock} disabled={isBusy || !state}>
          {state?.is_locked ? (
            <>
              <LockOpen className="size-3.5" /> Allow self-service
            </>
          ) : (
            <>
              <Lock className="size-3.5" /> Lock self-service
            </>
          )}
        </Button>
        <button type="button" className="text-11 text-tertiary underline" onClick={() => setIsOpen(false)}>
          Close
        </button>
      </div>
    </div>
  );
}
