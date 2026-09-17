/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { ParentPropertyIcon } from "@plane/propel/icons";
// components
import { IssueTypeIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// hooks
import { useWorkItemReference } from "@/hooks/use-work-item-reference";

type Props = {
  workItemId: string;
};

/** Icon of a parent or Epic group. Resolving it also loads the group's work item for the group title. */
export const WorkItemGroupIcon = observer(function WorkItemGroupIcon(props: Props) {
  const { workItemId } = props;
  const { workspaceSlug, projectId } = useParams();
  const workItem = useWorkItemReference(workspaceSlug?.toString(), projectId?.toString(), workItemId);

  if (workItem?.type_id && workItem.project_id)
    return <IssueTypeIdentifier issueTypeId={workItem.type_id} projectId={workItem.project_id} size="sm" />;
  return <ParentPropertyIcon className="h-3.5 w-3.5" />;
});
