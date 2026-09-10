/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
// plane imports
import type { TIssueServiceType, TWorkItemWidgets } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useTimeLineRelationOptions } from "@/components/relations";
// local imports
import { AttachmentsCollapsible } from "./attachments";
import { LinksCollapsible } from "./links";
import { RelationsCollapsible } from "./relations";
import { SubIssuesCollapsible } from "./sub-issues";
import { WorkshopSessionsCollapsible } from "./workshop-sessions";

type Props = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
  issueServiceType: TIssueServiceType;
  hideWidgets?: TWorkItemWidgets[];
};

export const IssueDetailWidgetCollapsibles = observer(function IssueDetailWidgetCollapsibles(props: Props) {
  const { workspaceSlug, projectId, issueId, disabled, issueServiceType, hideWidgets } = props;
  // store hooks
  const {
    issue: { getIssueById },
    subIssues: { subIssuesByIssueId },
    attachment: { getAttachmentsCountByIssueId, getAttachmentsUploadStatusByIssueId },
    relation: { getRelationCountByIssueId },
  } = useIssueDetail(issueServiceType);
  // derived values
  const issue = getIssueById(issueId);
  const subIssues = subIssuesByIssueId(issueId);
  const ISSUE_RELATION_OPTIONS = useTimeLineRelationOptions();
  const issueRelationsCount = getRelationCountByIssueId(issueId, ISSUE_RELATION_OPTIONS);
  // render conditions
  const shouldRenderSubIssues = !!subIssues && subIssues.length > 0 && !hideWidgets?.includes("sub-work-items");
  const shouldRenderRelations = issueRelationsCount > 0 && !hideWidgets?.includes("relations");
  const shouldRenderLinks = !!issue?.link_count && issue?.link_count > 0 && !hideWidgets?.includes("links");
  const attachmentUploads = getAttachmentsUploadStatusByIssueId(issueId);
  const attachmentsCount = getAttachmentsCountByIssueId(issueId);
  const shouldRenderAttachments =
    attachmentsCount > 0 ||
    (!!attachmentUploads && attachmentUploads.length > 0 && !hideWidgets?.includes("attachments"));

  return (
    <div className="flex flex-col">
      {shouldRenderSubIssues && (
        <SubIssuesCollapsible
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          issueId={issueId}
          disabled={disabled}
          issueServiceType={issueServiceType}
        />
      )}
      {shouldRenderRelations && (
        <RelationsCollapsible
          workspaceSlug={workspaceSlug}
          issueId={issueId}
          disabled={disabled}
          issueServiceType={issueServiceType}
        />
      )}
      {shouldRenderLinks && (
        <LinksCollapsible
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          issueId={issueId}
          disabled={disabled}
          issueServiceType={issueServiceType}
        />
      )}
      {/* Fork (see FORK.md): workshop sessions are a Hangar work item type. The
          component returns null for every other type, so this costs nothing on
          an upstream work item. Mounted here rather than in the properties
          sidebar because the session editor needs the body's width -- and
          because this host renders in the peek panel too, which never showed it. */}
      <WorkshopSessionsCollapsible
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        issueId={issueId}
        issueTypeId={issue?.type_id ?? null}
        assigneeIds={issue?.assignee_ids ?? []}
        disabled={disabled}
      />
      {shouldRenderAttachments && (
        <AttachmentsCollapsible
          workspaceSlug={workspaceSlug}
          projectId={projectId}
          issueId={issueId}
          disabled={disabled}
          issueServiceType={issueServiceType}
        />
      )}
    </div>
  );
});
