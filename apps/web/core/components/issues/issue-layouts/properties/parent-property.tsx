/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { MouseEvent } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useTranslation } from "@plane/i18n";
import { ParentPropertyIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIssue } from "@plane/types";
import { cn } from "@plane/utils";
// components
import { IssueIdentifier } from "@/components/issues/issue-detail/issue-identifier";
// hooks
import useIssuePeekOverviewRedirection from "@/hooks/use-issue-peek-overview-redirection";
import { usePlatformOS } from "@/hooks/use-platform-os";
import { useWorkItemReference } from "@/hooks/use-work-item-reference";

type Props = {
  issue: TIssue;
  className?: string;
};

/** The parent of a work item, shown as its identifier and name. Opens the parent in peek view. */
export const WorkItemParentProperty = observer(function WorkItemParentProperty(props: Props) {
  const { issue, className } = props;
  const { t } = useTranslation();
  const { workspaceSlug } = useParams();
  const { isMobile } = usePlatformOS();
  const { handleRedirection } = useIssuePeekOverviewRedirection();
  const parent = useWorkItemReference(workspaceSlug?.toString(), issue.project_id, issue.parent_id);

  if (!issue.parent_id) return null;

  const openParent = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    event.preventDefault();
    if (parent) handleRedirection(workspaceSlug?.toString(), parent, isMobile);
  };

  return (
    <Tooltip
      tooltipHeading={t("common.parent")}
      tooltipContent={parent?.name ?? t("common.parent")}
      isMobile={isMobile}
      renderByDefault={false}
    >
      <button
        type="button"
        onClick={openParent}
        disabled={!parent}
        className={cn(
          "flex h-5 max-w-56 min-w-0 flex-shrink-0 items-center gap-1.5 overflow-hidden rounded-sm border-[0.5px] border-strong px-2 text-caption-sm-regular",
          { "hover:bg-layer-1": parent },
          className
        )}
      >
        {parent?.project_id ? (
          <IssueIdentifier issueId={parent.id} projectId={parent.project_id} size="xs" variant="tertiary" />
        ) : (
          <ParentPropertyIcon className="size-3 flex-shrink-0" />
        )}
        <span className="truncate">{parent?.name ?? t("common.parent")}</span>
      </button>
    </Tooltip>
  );
});
