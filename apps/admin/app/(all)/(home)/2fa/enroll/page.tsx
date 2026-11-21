/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { startRegistration } from "@simplewebauthn/browser";
import { useRouter } from "next/navigation";
// plane internal packages
import { Banner } from "@makeplane/propel/components/banner";
import { Button } from "@makeplane/propel/components/button";
import { InputField } from "@makeplane/propel/components/input-field";
import { AuthService, InstanceWebAuthnService } from "@plane/services";
import { GOD_MODE_URL } from "@plane/constants";
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
        return undefined;
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
        <h1 className="text-h4-semibold text-primary">Register a security key</h1>
        <p className="text-body-sm-regular text-tertiary">
          This console requires a security key in addition to your password. Register one now to continue — a lost key
          can only be reset from a shell on the server, so a second key is worth adding afterwards.
        </p>
      </div>

      {error && <Banner placement="inline" variant="danger" description={error} />}

      {supported ? (
        <>
          <InputField
            size="lg"
            orientation="vertical"
            label="Key name"
            value={nickname}
            onChange={(event) => setNickname(event.target.value)}
            placeholder="Name this key, e.g. YubiKey 5C"
          />
          <Button
            variant="primary"
            size="lg"
            stretch="full"
            onClick={() => void register()}
            loading={isBusy}
            disabled={!csrfToken || isBusy}
            label={isBusy ? "Waiting for your key..." : "Register security key"}
          />
        </>
      ) : (
        <Banner
          placement="inline"
          variant="danger"
          description="This browser does not support security keys. Open the console in a browser that does."
        />
      )}
    </div>
  );
}

export const meta: Route.MetaFunction = () => [{ title: "Register a security key - God Mode" }];
