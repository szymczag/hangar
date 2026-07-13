/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// ui
import { ISSUE_TRACKER_URL } from "@plane/constants";
import { Button } from "@plane/propel/button";

function ErrorPage() {
  const handleRetry = () => {
    window.location.reload();
  };

  return (
    <div className="grid h-screen place-items-center bg-surface-1 p-4">
      <div className="space-y-8 text-center">
        <div className="space-y-2">
          <h3 className="text-16 font-semibold">Hangar could not load this page</h3>
          <p className="mx-auto text-13 text-secondary md:w-1/2">
            Refresh the page and try again. If the problem persists, open a GitHub issue with the steps that led here.
            Do not include secrets or private workspace data.
          </p>
        </div>
        <div className="flex items-center justify-center gap-2">
          <Button variant="primary" size="lg" onClick={handleRetry}>
            Refresh
          </Button>
          <a href={ISSUE_TRACKER_URL} target="_blank" rel="noreferrer">
            <Button variant="secondary" size="lg">
              Open a GitHub issue
            </Button>
          </a>
          {/* <Button variant="secondary" size="lg" onClick={() => {}}>
            Sign out
          </Button> */}
        </div>
      </div>
    </div>
  );
}

export default ErrorPage;
