/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { startAuthentication } from "@simplewebauthn/browser";
import { useRouter } from "next/navigation";
// plane internal packages
import { Button } from "@plane/propel/button";
import { AuthService, InstanceWebAuthnService } from "@plane/services";
// components
import { Banner } from "@/components/common/banner";
// types
import type { Route } from "./+types/page";

const authService = new AuthService();
const webAuthnService = new InstanceWebAuthnService();

export default function AdminSecondFactorPage(_props: Route.ComponentProps) {
  const { replace } = useRouter();
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);
  const [email, setEmail] = useState<string>("");
  const [error, setError] = useState<string | undefined>(undefined);
  const [isBusy, setIsBusy] = useState(false);
  const supported = typeof window !== "undefined" && Boolean(window.PublicKeyCredential);

  useEffect(() => {
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
  }, []);

  // The session endpoint is the authority on which step applies; the redirect
  // that landed here only chose the initial page.
  useEffect(() => {
    fetch(`${window.location.origin}/api/instances/admins/session/`, { credentials: "include" })
      .then((response) => response.json())
      .then((data) => {
        if (data?.is_2fa_pending !== true) replace("/");
        else if (data?.requires_enrollment === true) replace("/2fa/enroll");
        else setEmail(data?.email ?? "");
      })
      .catch(() => replace("/"));
  }, [replace]);

  const unlock = async () => {
    if (!csrfToken) return;
    setIsBusy(true);
    setError(undefined);
    try {
      const { options } = await webAuthnService.authenticationOptions(csrfToken);
      const parsed = JSON.parse(options);
      // A user gesture is required for navigator.credentials.get, which is why
      // this hangs off a button rather than running on mount.
      const credential = await startAuthentication({ optionsJSON: parsed });
      const { redirect_url } = await webAuthnService.verifyAuthentication(csrfToken, {
        credential,
        challenge: parsed.challenge,
      });
      window.location.assign(redirect_url);
    } catch (caught: unknown) {
      const name = (caught as { name?: string })?.name;
      if (name === "NotAllowedError") setError("The request was cancelled or timed out. Try again.");
      else if (name === "SecurityError")
        setError("This site is not allowed to use your security key. Check WEBAUTHN_RP_ID for this deployment.");
      else setError((caught as { error_message?: string })?.error_message ?? "That key could not be verified.");
      setIsBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-md space-y-6 py-16">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Confirm it is you</h1>
        <p className="text-sm text-tertiary">
          {email ? `Signed in as ${email}. ` : ""}This console requires a security key in addition to your password.
        </p>
      </div>

      {error && <Banner type="error" message={error} />}

      {supported ? (
        <Button variant="primary" onClick={unlock} loading={isBusy} disabled={!csrfToken || isBusy}>
          {isBusy ? "Waiting for your key..." : "Unlock with your security key"}
        </Button>
      ) : (
        <Banner
          type="error"
          message="This browser does not support security keys. Open the console in a browser that does."
        />
      )}

      <form method="POST" action={`${window.location.origin}/api/instances/admins/sign-out/`}>
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <button type="submit" className="text-sm text-tertiary underline">
          Start over
        </button>
      </form>
    </div>
  );
}

export const meta: Route.MetaFunction = () => [{ title: "Security key - God Mode" }];
