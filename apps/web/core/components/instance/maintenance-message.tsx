/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export function MaintenanceMessage() {
  const linkMap = [
    {
      key: "issues",
      label: "Open a GitHub issue",
      value: "https://github.com/szymczag/hangar/issues",
    },
  ];

  return (
    <>
      <div className="flex flex-col gap-2.5">
        <h1 className="text-left text-18 font-semibold text-primary">&#x1F6A7; Hangar didn&apos;t start correctly</h1>
        <span className="text-left text-14 font-medium text-secondary">
          Some services might have failed to start. Please check your container logs to identify and resolve the issue.
          If the problem persists, open a GitHub issue and include the relevant logs.
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
