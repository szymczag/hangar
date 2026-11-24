/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";

import { useTranslation } from "@plane/i18n";
import { AddOutline } from "@makeplane/propel/icons";
import type { TQuickAddIssueButton } from "../root";

export const KanbanQuickAddIssueButton = observer(function KanbanQuickAddIssueButton(props: TQuickAddIssueButton) {
  const { onClick, isEpic = false } = props;
  const { t } = useTranslation();
  return (
    <button
      type="button"
      className="flex w-full cursor-pointer items-center gap-2 rounded-lg bg-layer-1 px-2 py-1 text-left hover:bg-layer-transparent-hover focus-visible:ring-2 focus-visible:ring-accent-strong focus-visible:outline-none"
      onClick={onClick}
    >
      <AddOutline className="h-3.5 w-3.5" />
      <span className="text-body-xs-medium">{isEpic ? t("epic.new") : t("issue.new")}</span>
    </button>
  );
});
