/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { startRegistration } from "@simplewebauthn/browser";
import { useRouter } from "next/navigation";
// plane internal packages
import { Button } from "@plane/propel/button";
import { AuthService, InstanceWebAuthnService } from "@plane/services";
import { GOD_MODE_URL } from "@plane/constants";
// components
import { Banner } from "@/components/common/banner";
// helpers
import { authErrorHandler } from "../../auth-helpers";
// types
import type { Route } from "./+types/page";

const authService = new AuthService();
const webAuthnService = new InstanceWebAuthnService();

export default function AdminSecondFactorEnrollPage(_props: Route.ComponentProps) {
  const { replace } = useRouter();
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [isBusy, setIsBusy] = useState(false);
  const supported = typeof window !== "undefined" && Boolean(window.PublicKeyCredential);

  useEffect(() => {
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
  }, []);

  useEffect(() => {
    fetch(`${window.location.origin}/api/instances/admins/session/`, { credentials: "include" })
      .then((response) => response.json())
      .then((data) => {
        if (data?.is_2fa_pending !== true) replace("/");
        else if (data?.requires_enrollment === false) replace("/2fa");
      })
      .catch(() => replace("/"));
  }, [replace]);

  const register = async () => {
    if (!csrfToken) return;
    setIsBusy(true);
    setError(undefined);
    try {
      const { options, user_handle } = await webAuthnService.registrationOptions(csrfToken);
      const parsed = JSON.parse(options);
      const credential = await startRegistration({ optionsJSON: parsed });
      const { redirect_url } = await webAuthnService.verifyRegistration(csrfToken, {
        credential,
        challenge: parsed.challenge,
        user_handle,
        nickname: nickname.trim() || "Security key",
      });
      // The console is mounted under ADMIN_BASE_PATH, so a bare "/general/"
      // would 404. Only the add-a-second-key response omits redirect_url.
      window.location.assign(redirect_url ?? `${GOD_MODE_URL}general/`);
    } catch (caught: unknown) {
      const name = (caught as { name?: string })?.name;
      if (name === "InvalidStateError") setError("That key is already registered on this account.");
      else if (name === "NotAllowedError") setError("The request was cancelled or timed out. Try again.");
      else if (name === "SecurityError")
        setError("This site is not allowed to use your security key. Check WEBAUTHN_RP_ID for this deployment.");
      else {
        const code = (caught as { error_code?: string })?.error_code;
        const known = code ? authErrorHandler(code as never) : undefined;
        // message is already resolved to a node; the second-factor copy is
        // plain text, so anything else falls back rather than rendering oddly.
        setError(typeof known?.message === "string" ? known.message : "That key could not be registered.");
      }
      setIsBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-md space-y-6 py-16">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Register a security key</h1>
        <p className="text-sm text-tertiary">
          This console requires a security key in addition to your password. Register one now to continue — a lost key
          can only be reset from a shell on the server, so a second key is worth adding afterwards.
        </p>
      </div>

      {error && <Banner type="error" message={error} />}

      {supported ? (
        <>
          <input
            value={nickname}
            onChange={(event) => setNickname(event.target.value)}
            placeholder="Name this key, e.g. YubiKey 5C"
            className="text-sm w-full rounded-sm border border-strong bg-surface-1 px-3 py-2 outline-none"
          />
          <Button variant="primary" onClick={register} loading={isBusy} disabled={!csrfToken || isBusy}>
            {isBusy ? "Waiting for your key..." : "Register security key"}
          </Button>
        </>
      ) : (
        <Banner
          type="error"
          message="This browser does not support security keys. Open the console in a browser that does."
        />
      )}
    </div>
  );
}

export const meta: Route.MetaFunction = () => [{ title: "Register a security key - God Mode" }];
