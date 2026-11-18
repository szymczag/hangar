/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRouter } from "next/navigation";
// types
import type { TIssue } from "@plane/types";
// helpers
import { generateWorkItemLink } from "@plane/utils";
// hooks
import { useIssueDetail } from "./store/use-issue-detail";
import { useProject } from "./store/use-project";

// The argument remains for source compatibility with layout callers. Epic and
// Task now share the same detail store and redirection behavior.
const useIssuePeekOverviewRedirection = (_isEpic: boolean = false) => {
  // router
  const router = useRouter();
  //   store hooks
  const { getIsIssuePeeked, setPeekIssue } = useIssueDetail();
  const { getProjectIdentifierById } = useProject();

  const handleRedirection = (
    workspaceSlug: string | undefined,
    issue: TIssue | undefined,
    isMobile = false,
    nestingLevel?: number
  ) => {
    if (!issue) return;
    const { project_id, id, archived_at, tempId } = issue;
    const projectIdentifier = getProjectIdentifierById(issue?.project_id);

    const workItemLink = generateWorkItemLink({
      workspaceSlug,
      projectId: project_id,
      issueId: id,
      projectIdentifier,
      sequenceId: issue?.sequence_id,
      isArchived: !!archived_at,
    });
    if (workspaceSlug && project_id && id && !getIsIssuePeeked(id) && !tempId) {
      if (isMobile) {
        router.push(workItemLink);
      } else {
        setPeekIssue({ workspaceSlug, projectId: project_id, issueId: id, nestingLevel, isArchived: !!archived_at });
      }
    }
  };

  return { handleRedirection };
};

export default useIssuePeekOverviewRedirection;
