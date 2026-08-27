/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { recalledFailurePageBranding } from "@/helpers/failure-page-branding";

export function MaintenanceMessage() {
  // The instance could not be reached, so what to say here was remembered from
  // the last time it could. An operator running this inside a company puts their
  // own help desk on this screen; without one, it says nothing about where to go,
  // which is better than sending staff to a public issue tracker at the moment
  // their tools stopped working.
  const { supportText, showExternalLinks } = recalledFailurePageBranding();
  const linkMap = showExternalLinks
    ? [
        {
          key: "issues",
          label: "Open a GitHub issue",
          value: "https://github.com/szymczag/hangar/issues",
        },
      ]
    : [];

  return (
    <>
      <div className="flex flex-col gap-2.5">
        <h1 className="text-left text-18 font-semibold text-primary">&#x1F6A7; Hangar didn&apos;t start correctly</h1>
        <span className="text-left text-14 font-medium text-secondary">
          {supportText ? (
            supportText
          ) : showExternalLinks ? (
            <>
              Some services might have failed to start. Please check your container logs to identify and resolve the
              issue. If the problem persists, open a GitHub issue and include the relevant logs.
            </>
          ) : (
            <>Some services might have failed to start. Please try again shortly.</>
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
    </>
  );
}
