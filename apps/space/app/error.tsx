/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// ui
import { Button } from "@makeplane/propel/components/button";
import { ISSUE_TRACKER_URL } from "@plane/constants";

const handleRetry = () => {
  window.location.reload();
};

function ErrorPage() {
  return (
    <div className="grid h-screen place-items-center bg-surface-1 p-4">
      <div className="space-y-8 text-center">
        <div className="space-y-2">
          <h3 className="text-h6-semibold">Hangar could not load this page</h3>
          <p className="mx-auto text-body-xs-regular text-secondary md:w-1/2">
            Refresh the page and try again. If the problem persists, open a GitHub issue with the steps that led here.
            Do not include secrets or private workspace data.
          </p>
        </div>
        <div className="flex items-center justify-center gap-2">
          <Button variant="primary" size="md" stretch="auto" label="Refresh" onClick={handleRetry} />
          <Button
            variant="secondary"
            size="md"
            stretch="auto"
            label="Open a GitHub issue"
            nativeButton={false}
            render={<a href={ISSUE_TRACKER_URL} target="_blank" rel="noreferrer" aria-label="Open a GitHub issue" />}
          />
          {/* <Button variant="secondary" size="lg" onClick={() => {}}>
            Sign out
          </Button> */}
        </div>
      </div>
    </div>
  );
}

export default ErrorPage;
