/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useTheme } from "next-themes";
// plane imports
import { ISSUE_TRACKER_URL, SOURCE_CODE_URL } from "@plane/constants";
import { Button } from "@plane/propel/button";
// assets
import maintenanceModeDarkModeImage from "@/app/assets/instance/maintenance-mode-dark.svg?url";
import maintenanceModeLightModeImage from "@/app/assets/instance/maintenance-mode-light.svg?url";
// layouts
import { recalledFailurePageBranding } from "@/helpers/failure-page-branding";
import DefaultLayout from "@/layouts/default-layout";

// The source offer is not conditional: AGPL-3.0 section 13 requires it of anyone
// running a modified version over a network, and a page rendering after a crash
// is still that version. The issue tracker is, because on a deployment inside a
// company nobody wants their staff filing public bug reports.
const sourceLink = {
  key: "source",
  label: "View source",
  value: SOURCE_CODE_URL,
};

const issueLink = {
  key: "report_issue",
  label: "Open a GitHub issue",
  value: ISSUE_TRACKER_URL,
};

// Production Error Component
interface ProdErrorComponentProps {
  onGoHome: () => void;
}

export function ProdErrorComponent({ onGoHome }: ProdErrorComponentProps) {
  // hooks
  const { resolvedTheme } = useTheme();

  // derived values
  const maintenanceModeImage = resolvedTheme === "dark" ? maintenanceModeDarkModeImage : maintenanceModeLightModeImage;
  // Remembered from the last successful start; this page renders after a crash,
  // when the instance cannot be asked.
  const { supportText, showExternalLinks } = recalledFailurePageBranding();
  const linkMap = showExternalLinks ? [issueLink, sourceLink] : [sourceLink];

  return (
    <DefaultLayout>
      <div className="relative container mx-auto flex h-full w-full max-w-xl flex-col items-center justify-center gap-2 gap-y-6 bg-surface-1 px-6 text-center">
        <div className="relative w-full">
          <img
            src={maintenanceModeImage}
            height="176"
            width="288"
            alt="ProjectSettingImg"
            className="h-full w-full object-fill object-center"
          />
        </div>
        <div className="relative mt-4 flex w-full flex-col gap-4">
          <div className="flex flex-col gap-2.5">
            <h1 className="text-left text-18 font-semibold text-primary">&#x1F6A7; Looks like something went wrong!</h1>
            <span className="text-left text-14 font-medium text-secondary">
              {supportText ? (
                supportText
              ) : showExternalLinks ? (
                <>
                  Refresh and try again. If the problem persists, open a GitHub issue with the steps that led here. Do
                  not include secrets or private workspace data.
                </>
              ) : (
                <>Refresh and try again. If the problem persists, report it to whoever runs this instance.</>
              )}
            </span>
          </div>

          <div className="mt-1 flex items-center justify-start gap-6">
            {linkMap.map((link) => (
              <div key={link.key}>
                <a
                  href={link.value}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-13 text-accent-primary hover:underline"
                >
                  {link.label}
                </a>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-start gap-6">
            <Button variant="primary" size="lg" onClick={onGoHome}>
              Go to home
            </Button>
          </div>
        </div>
      </div>
    </DefaultLayout>
  );
}
