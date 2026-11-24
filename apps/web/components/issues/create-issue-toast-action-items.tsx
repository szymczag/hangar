/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useState } from "react";
import type React from "react";
import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import type { ToastActionItem } from "@plane/blocks/toast";
import { copyTextToClipboard, copyUrlToClipboard, generateWorkItemLink } from "@plane/utils";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useProject } from "@/hooks/store/use-project";

type TCreateIssueToastActionArgs = {
  workspaceSlug: string;
  issueId: string;
  isEpic?: boolean;
};

/**
 * propel: Propel's toast is a closed, portaled surface with no markup escape hatch, so its actions
 * cross the boundary as data (`{ label, onClick | href }`) — a component here would be dropped at
 * runtime. This hook keeps the store reads (the work item is only in the store once the create
 * settles) and hands the call site a builder it can invoke inside `setToast`.
 */
export function useCreateIssueToastActions() {
  const { t } = useTranslation();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getProjectIdentifierById } = useProject();

  return useCallback(
    ({ workspaceSlug, issueId, isEpic = false }: TCreateIssueToastActionArgs): ToastActionItem[] => {
      const issue = getIssueById(issueId);
      if (!issue) return [];

      const projectIdentifier = getProjectIdentifierById(issue.project_id);
      const hasIdentifier = !!(projectIdentifier && issue.sequence_id);
      if (!hasIdentifier) return [];

      const identifier = `${projectIdentifier}-${issue.sequence_id}`;
      const workItemLink = generateWorkItemLink({
        workspaceSlug,
        projectId: issue.project_id,
        issueId,
        projectIdentifier,
        sequenceId: issue.sequence_id,
        isEpic,
      });
      if (!workItemLink) return [];

      // Propel renders two left actions plus one right-aligned `primary`, so all three fit: view
      // takes the primary slot (it is the call to action on a success toast) and the two copy
      // affordances the old markup offered stay in the left cluster.
      return [
        {
          label: t("common.actions.copy_link"),
          onClick: () => {
            void copyUrlToClipboard(workItemLink);
          },
        },
        {
          label: identifier,
          onClick: () => {
            void copyTextToClipboard(identifier);
          },
        },
        { label: t("common.view"), href: workItemLink, target: "_blank", primary: true },
      ];
    },
    [t, getIssueById, getProjectIdentifierById]
  );
}

type TCreateIssueToastActionItems = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  isEpic?: boolean;
};

/**
 * Fork: compatibility shim, removed in phase 9.
 *
 * The 1.4 markup the create/edit dialog (`issue-modal/base.tsx`) still hands the 1.4 toast until the
 * dialog moves to Propel (phase 4c). Everything else builds the actions with the hook above.
 */
export const CreateIssueToastActionItems = observer(function CreateIssueToastActionItems(
  props: TCreateIssueToastActionItems
) {
  const { workspaceSlug, issueId, isEpic = false } = props;
  // state
  const [copied, setCopied] = useState(false);
  // store hooks
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getProjectIdentifierById } = useProject();

  // derived values
  const issue = getIssueById(issueId);
  const projectIdentifier = getProjectIdentifierById(issue?.project_id);

  if (!issue) return null;

  const workItemLink = generateWorkItemLink({
    workspaceSlug,
    projectId: issue?.project_id,
    issueId,
    projectIdentifier,
    sequenceId: issue?.sequence_id,
    isEpic,
  });

  const copyToClipboard = async (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
    try {
      await copyUrlToClipboard(workItemLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch (_error) {
      setCopied(false);
    }
    e.preventDefault();
    e.stopPropagation();
  };

  return (
    <div className="-ml-2 flex items-center gap-1 text-11 text-secondary">
      <a
        href={workItemLink}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded-sm px-2 py-1 font-medium text-accent-primary hover:bg-surface-2"
      >
        {`View ${isEpic ? "epic" : "work item"}`}
      </a>

      {copied ? (
        <>
          <span className="cursor-default px-2 py-1 text-secondary">Copied!</span>
        </>
      ) : (
        <>
          <button
            className="hidden cursor-pointer rounded-sm px-2 py-1 text-tertiary group-hover:flex hover:bg-surface-2 hover:text-secondary"
            onClick={copyToClipboard}
          >
            Copy link
          </button>
        </>
      )}
    </div>
  );
});
