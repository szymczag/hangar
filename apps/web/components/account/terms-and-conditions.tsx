/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import Link from "next/link";
import { EAuthModes, PRIVACY_URL, SOURCE_CODE_URL, TERMS_URL } from "@plane/constants";
import { useInstance } from "@/hooks/store/use-instance";

interface TermsAndConditionsProps {
  authType?: EAuthModes;
}

const MESSAGES = {
  [EAuthModes.SIGN_UP]: "By creating an account",
  [EAuthModes.SIGN_IN]: "By signing in",
} as const;

// Reusable link component to reduce duplication
function LegalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="text-secondary" target="_blank" rel="noopener noreferrer">
      <span className="text-13 font-medium underline hover:cursor-pointer">{children}</span>
    </Link>
  );
}

export function TermsAndConditions({ authType = EAuthModes.SIGN_IN }: TermsAndConditionsProps) {
  const { config } = useInstance();
  const termsUrl = config?.product?.terms_url ?? TERMS_URL;
  const privacyUrl = config?.product?.privacy_url ?? PRIVACY_URL;
  const sourceUrl = config?.product?.source_url ?? SOURCE_CODE_URL;

  // Turned off from God Mode for a plain sign-in page. The offer itself is not
  // optional — AGPL-3.0 section 13 requires it of anyone running a modified
  // version over a network — so it stays in the in-app help menu, which every
  // signed-in person reaches and which this setting does not touch.
  const showLicenseNotice = config?.show_license_notice !== false;
  const hasLegalLinks = Boolean(termsUrl || privacyUrl);

  if (!hasLegalLinks && !showLicenseNotice) return null;

  return (
    <div className="flex flex-col items-center justify-center gap-1">
      {hasLegalLinks && (
        <p className="text-center text-13 whitespace-pre-line text-tertiary">
          {MESSAGES[authType]}
          {termsUrl && (
            <>
              {", you agree to the "}
              <LegalLink href={termsUrl}>Terms of Service</LegalLink>
            </>
          )}
          {privacyUrl && (
            <>
              {termsUrl ? " and acknowledge the " : ", you acknowledge the "}
              <LegalLink href={privacyUrl}>Privacy Policy</LegalLink>
            </>
          )}
          {"."}
        </p>
      )}
      {/* Previously this appeared only when neither legal URL was set, so
          configuring terms and privacy dropped the source offer without anyone
          deciding to. The two are separate statements and now render as such. */}
      {showLicenseNotice && (
        <p className="text-center text-13 text-tertiary">
          Hangar is open-source software under the AGPL-3.0 license.{" "}
          <LegalLink href={sourceUrl}>View source code</LegalLink>.
        </p>
      )}
    </div>
  );
}
