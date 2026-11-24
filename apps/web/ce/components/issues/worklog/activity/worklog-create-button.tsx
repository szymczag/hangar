/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { AddTimeTrackingOutline } from "@makeplane/propel/icons";
// hooks
import { useProject } from "@/hooks/store/use-project";
// plane web
import { WorklogModal } from "../worklog-modal";

type TIssueActivityWorklogCreateButton = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
  canViewWorklogs: boolean;
};

export const IssueActivityWorklogCreateButton = observer(function IssueActivityWorklogCreateButton(
  props: TIssueActivityWorklogCreateButton
) {
  const { workspaceSlug, projectId, issueId, disabled, canViewWorklogs } = props;
  // state
  const [isModalOpen, setIsModalOpen] = useState(false);
  // store hooks
  const { getProjectById } = useProject();
  // derived values
  const isTimeTrackingEnabled = Boolean(getProjectById(projectId)?.is_time_tracking_enabled);

  if (!isTimeTrackingEnabled || !canViewWorklogs) return <></>;

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        stretch="auto"
        label="Log time"
        icon={<Icon icon={AddTimeTrackingOutline} />}
        onClick={() => setIsModalOpen(true)}
        disabled={disabled}
      />
      <WorklogModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        workspaceSlug={workspaceSlug}
        projectId={projectId}
        issueId={issueId}
        disabled={disabled}
        canViewWorklogs={canViewWorklogs}
      />
    </>
  );
});
