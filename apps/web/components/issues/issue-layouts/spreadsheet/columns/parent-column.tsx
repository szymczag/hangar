/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import type { TIssue } from "@plane/types";
import { Row } from "@plane/ui";
// components
import { WorkItemParentProperty } from "../../properties/parent-property";

type Props = {
  issue: TIssue;
};

export const SpreadsheetParentColumn = observer(function SpreadsheetParentColumn(props: Props) {
  const { issue } = props;

  return (
    <Row className="flex h-11 w-full items-center border-b-[0.5px] border-subtle py-1 group-[.selected-issue-row]:bg-accent-primary/5 hover:bg-surface-2">
      <WorkItemParentProperty issue={issue} className="border-0 px-0" />
    </Row>
  );
});
