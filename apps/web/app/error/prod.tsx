/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { ISSUE_TRACKER_URL, SOURCE_CODE_URL } from "@plane/constants";
import { AnchorButton } from "@makeplane/propel/components/anchor-button";
import { Button } from "@makeplane/propel/components/button";
import { EmptyStateDetailed } from "@plane/blocks/empty-state";
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
  onReload: () => void;
}

export function ProdErrorComponent({ onGoHome, onReload }: ProdErrorComponentProps) {
  // Remembered from the last successful start; this page renders after a crash,
  // when the instance cannot be asked.
  const { supportText, showExternalLinks } = recalledFailurePageBranding();
  const linkMap = showExternalLinks ? [issueLink, sourceLink] : [sourceLink];
  const description =
    supportText ||
    (showExternalLinks
      ? "Refresh and try again. If the problem persists, open a GitHub issue with the steps that led here. Do not include secrets or private workspace data."
      : "Refresh and try again. If the problem persists, report it to whoever runs this instance.");

  return (
    <DefaultLayout>
      {/* The blocks illustration is themed through CSS tokens, so no theme lookup is needed here. */}
      <div className="size-full px-6">
        <EmptyStateDetailed
          align="center"
          assetKey="server-error"
          assetClassName="size-40"
          title="🚧 Looks like something went wrong!"
          description={description}
          customButton={
            <div className="flex flex-col items-center gap-4">
              <div className="flex flex-wrap items-center justify-center gap-6">
                {linkMap.map((link) => (
                  <AnchorButton
                    key={link.key}
                    variant="primary"
                    size="sm"
                    href={link.value}
                    target="_blank"
                    rel="noopener noreferrer"
                    label={link.label}
                  />
                ))}
              </div>
              <div className="flex flex-col gap-4 sm:flex-row">
                <Button variant="primary" size="lg" stretch="auto" label="Reload" onClick={onReload} />
                <Button variant="secondary" size="lg" stretch="auto" label="Go to home" onClick={onGoHome} />
              </div>
            </div>
          }
        />
      </div>
    </DefaultLayout>
  );
}
