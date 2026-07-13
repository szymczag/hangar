/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { PRIVACY_URL, SOURCE_CODE_URL, TERMS_URL } from "@plane/constants";
import { useInstance } from "@/hooks/store/use-instance";

type Props = {
  isSignUp?: boolean;
};

export function TermsAndConditions(props: Props) {
  const { isSignUp = false } = props;
  const { config } = useInstance();
  const termsUrl = config?.product?.terms_url ?? TERMS_URL;
  const privacyUrl = config?.product?.privacy_url ?? PRIVACY_URL;
  const sourceUrl = config?.product?.source_url ?? SOURCE_CODE_URL;

  if (!termsUrl && !privacyUrl) {
    return (
      <span className="flex items-center justify-center py-6">
        <p className="text-center text-13 text-secondary">
          Hangar is open-source software under the AGPL-3.0 license.{" "}
          <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="font-medium underline">
            View source code
          </a>
          .
        </p>
      </span>
    );
  }

  return (
    <span className="flex items-center justify-center py-6">
      <p className="text-center text-13 whitespace-pre-line text-secondary">
        {isSignUp ? "By creating an account" : "By signing in"}
        {termsUrl && (
          <>
            {", you agree to the "}
            <a href={termsUrl} target="_blank" rel="noopener noreferrer">
              <span className="text-13 font-medium underline hover:cursor-pointer">Terms of Service</span>
            </a>
          </>
        )}
        {privacyUrl && (
          <>
            {termsUrl ? " and acknowledge the " : ", you acknowledge the "}
            <a href={privacyUrl} target="_blank" rel="noopener noreferrer">
              <span className="text-13 font-medium underline hover:cursor-pointer">Privacy Policy</span>
            </a>
          </>
        )}
        {"."}
      </p>
    </span>
  );
}
