/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TSelectionHelper } from "@/hooks/use-multiple-select";

type Props = {
  className?: string;
  selectionHelpers: TSelectionHelper;
};

/**
 * Fork (see FORK.md): Hangar has no bulk operations (`useBulkOperationStatus` is always false), so
 * there is no selection bar to show. Upstream renders an "upgrade" banner linking off-instance
 * here; Hangar renders nothing rather than an upsell or an ungated external link (S22).
 */
export function IssueBulkOperationsRoot(_props: Props) {
  return null;
}
