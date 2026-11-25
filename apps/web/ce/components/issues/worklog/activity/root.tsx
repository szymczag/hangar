/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { TimeTrackingOutline } from "@makeplane/propel/icons";
import type { TIssueActivityComment } from "@plane/types";
// components
import { IssueActivityBlockComponent } from "@/components/issues/issue-detail/issue-activity/activity/actions";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
// local imports
import { WorklogActivityMessage } from "./message";

type TIssueActivityWorklog = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  activityComment: TIssueActivityComment;
  ends?: "top" | "bottom";
};

export const IssueActivityWorklog = observer(function IssueActivityWorklog(props: TIssueActivityWorklog) {
  const { activityComment, ends } = props;
  // store hooks
  const {
    activity: { getActivityById },
  } = useIssueDetail();
  // derived values
  const activity = getActivityById(activityComment.id);

  if (!activity) return <></>;

  return (
    <IssueActivityBlockComponent
      icon={<TimeTrackingOutline className="size-3.5 text-secondary" aria-hidden="true" />}
      activityId={activityComment.id}
      ends={ends}
    >
      <WorklogActivityMessage verb={activity.verb} oldValue={activity.old_value} newValue={activity.new_value} />
    </IssueActivityBlockComponent>
  );
});
