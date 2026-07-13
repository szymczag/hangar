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

  if (!termsUrl && !privacyUrl) {
    return (
      <div className="flex items-center justify-center">
        <p className="text-center text-13 text-tertiary">
          Hangar is open-source software under the AGPL-3.0 license.{" "}
          <LegalLink href={sourceUrl}>View source code</LegalLink>.
        </p>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center">
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
    </div>
  );
}
