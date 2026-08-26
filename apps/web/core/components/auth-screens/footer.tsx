/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// hooks
import { useInstance } from "@/hooks/store/use-instance";

/**
 * Says whose instance this is, and what it runs on.
 *
 * What stood here was inherited Plane marketing — "Join 10,000+ teams building
 * with Hangar" above the logos of four companies that are not customers of this
 * deployment and never agreed to appear on its sign-in page. On a self-hosted
 * instance that is not persuasive, it is just wrong.
 */
export const AuthFooter = observer(function AuthFooter() {
  const { config } = useInstance();
  const brandingName = config?.branding_name?.trim();

  return (
    <div className="flex flex-col items-center gap-2">
      <span className="text-13 text-tertiary">
        Running Hangar, an open-source work management platform
        {brandingName ? <span className="text-secondary"> · {brandingName}</span> : null}
      </span>
    </div>
  );
});
