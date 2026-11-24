/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): Hangar's rows in the work item properties. Upstream
// v1.5.0 renders the detail sidebar and the peek from one component
// (`issue-detail/sidebar-sections.tsx`) with no slot for them, so it mounts
// this one: the workshop schedule summary (detail page only, as before), time
// tracking, and the work item type's custom properties.

import { observer } from "mobx-react";
// components
import { WorkshopScheduleProperty } from "@/components/issues/issue-detail/workshop-schedule";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useUserPermissions } from "@/hooks/store/user";
// plane web
import { WorkItemAdditionalSidebarProperties } from "@/plane-web/components/issues/issue-details/additional-properties";
import { IssueWorklogProperty } from "@/plane-web/components/issues/worklog/property/root";
import { canViewWorklogsForRole } from "@/plane-web/helpers/worklog";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
  isPeekView?: boolean;
};

export const WorkItemSidebarHangarProperties = observer(function WorkItemSidebarHangarProperties(props: Props) {
  const { workspaceSlug, projectId, issueId, disabled, isPeekView = false } = props;
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // derived values
  const issue = getIssueById(issueId);
  // Worklogs are confidential from guests (S20).
  const canViewWorklogs = canViewWorklogsForRole(getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug, projectId));

  if (!issue) return null;

  return (
    <>
      {!isPeekView && (
        <WorkshopScheduleProperty
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          issueId={issueId}
          issueTypeId={issue.type_id}
          assigneeIds={issue.assignee_ids ?? []}
        />
      )}
      <IssueWorklogProperty
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        issueId={issueId}
        disabled={disabled}
        canViewWorklogs={canViewWorklogs}
      />
      <WorkItemAdditionalSidebarProperties
        workItemId={issue.id}
        workItemTypeId={issue.type_id}
        projectId={projectId}
        workspaceSlug={workspaceSlug}
        isEditable={!disabled}
        isPeekView={isPeekView}
      />
    </>
  );
});
