/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// icons
import { Shapes } from "lucide-react";
// plane imports
import { Logo } from "@plane/propel/emoji-icon-picker";
import { EpicIcon, WorkItemsIcon } from "@plane/propel/icons";
import { Tooltip } from "@plane/propel/tooltip";
import type { TIssueIdentifierProps, TIssueIdentifierSize, TIssueTypeIdentifier, TLogoProps } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useProject } from "@/hooks/store/use-project";
import { IdentifierText } from "@/components/issues/issue-detail/identifier-text";
// plane web
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";

export const IssueIdentifier = observer(function IssueIdentifier(props: TIssueIdentifierProps) {
  const { projectId, variant, size, displayProperties, enableClickToCopyIdentifier = false } = props;
  // store hooks
  const { getProjectIdentifierById } = useProject();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  // Determine if the component is using store data or not
  const isUsingStoreData = "issueId" in props;
  // derived values
  const issue = isUsingStoreData ? getIssueById(props.issueId) : null;
  const projectIdentifier = isUsingStoreData ? getProjectIdentifierById(projectId) : props.projectIdentifier;
  const issueSequenceId = isUsingStoreData ? issue?.sequence_id : props.issueSequenceId;
  const issueTypeId = isUsingStoreData ? issue?.type_id : props.issueTypeId;
  const shouldRenderIssueID = displayProperties ? displayProperties.key : true;
  // Fork (see FORK.md): the work item type mark follows its own display property.
  const shouldRenderIssueType = !!issueTypeId && (displayProperties ? displayProperties.issue_type !== false : true);

  if (!shouldRenderIssueID && !shouldRenderIssueType) return null;

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      {shouldRenderIssueType && issueTypeId && (
        <IssueTypeIdentifier issueTypeId={issueTypeId} projectId={projectId} size={size} />
      )}
      {shouldRenderIssueID && (
        <IdentifierText
          identifier={`${projectIdentifier}-${issueSequenceId}`}
          enableClickToCopyIdentifier={enableClickToCopyIdentifier}
          variant={variant}
          size={size}
        />
      )}
    </div>
  );
});
const TYPE_ICON_SIZE: Record<TIssueIdentifierSize, number> = { xs: 14, sm: 14, md: 16, lg: 16 };

// Fork (see FORK.md): a work item type is marked by its configured logo. Types
// without one fall back to a stable mark per system type.
export const IssueTypeIdentifier = observer(function IssueTypeIdentifier(props: TIssueTypeIdentifier) {
  const { issueTypeId, projectId, size = "md" } = props;
  const { workspaceSlug } = useParams();
  const { getTypeById } = useIssueTypes(workspaceSlug?.toString(), projectId);
  const issueType = getTypeById(issueTypeId);
  if (!issueType) return null;

  const iconSize = TYPE_ICON_SIZE[size];
  const logo = issueType.logo_props;
  const hasLogo = (logo?.in_use === "emoji" && !!logo.emoji?.value) || (logo?.in_use === "icon" && !!logo.icon?.name);
  let icon;
  if (hasLogo) {
    icon = <Logo logo={logo as TLogoProps} size={iconSize} />;
  } else if (issueType.system_key === "epic") {
    icon = <EpicIcon width={iconSize} height={iconSize} className="text-accent-primary" />;
  } else if (issueType.system_key === "task") {
    icon = <WorkItemsIcon width={iconSize} height={iconSize} className="text-tertiary" />;
  } else {
    icon = <Shapes style={{ width: iconSize, height: iconSize }} className="text-tertiary" />;
  }

  return (
    <Tooltip tooltipContent={issueType.name}>
      <span className="grid flex-shrink-0 place-items-center" aria-label={issueType.name}>
        {icon}
      </span>
    </Tooltip>
  );
});
