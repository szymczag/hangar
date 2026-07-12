/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { Timer } from "lucide-react";
// plane imports
import type { TIssueActivityComment } from "@plane/types";
// components
import { IssueActivityBlockComponent } from "@/components/issues/issue-detail/issue-activity/activity/actions";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";

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
      icon={<Timer size={14} className="text-secondary" aria-hidden="true" />}
      activityId={activityComment.id}
      ends={ends}
    >
      {activity.verb === "created" ? (
        <>
          logged <span className="font-medium text-primary">{activity.new_value}</span>
        </>
      ) : activity.verb === "updated" ? (
        <>
          updated logged time from <span className="font-medium text-primary">{activity.old_value}</span> to{" "}
          <span className="font-medium text-primary">{activity.new_value}</span>
        </>
      ) : (
        <>
          removed logged time <span className="font-medium text-primary">{activity.old_value}</span>
        </>
      )}
    </IssueActivityBlockComponent>
  );
});
