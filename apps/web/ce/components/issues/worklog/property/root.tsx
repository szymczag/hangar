/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Timer } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
// components
import { SidebarPropertyListItem } from "@/components/common/layout/sidebar/property-list-item";
// hooks
import { useProject } from "@/hooks/store/use-project";
// plane web
import { formatWorklogDuration } from "@/plane-web/helpers/worklog";
import { useWorklogs } from "@/plane-web/hooks/use-worklogs";
import { WorklogModal } from "../worklog-modal";

type TIssueWorklogProperty = {
  workspaceSlug: string;
  projectId: string;
  issueId: string;
  disabled: boolean;
  canViewWorklogs: boolean;
};

export const IssueWorklogProperty = observer(function IssueWorklogProperty(props: TIssueWorklogProperty) {
  const { workspaceSlug, projectId, issueId, disabled, canViewWorklogs } = props;
  // i18n
  const { t } = useTranslation();
  // state
  const [isModalOpen, setIsModalOpen] = useState(false);
  // store hooks
  const { getProjectById } = useProject();
  // derived values
  const isTimeTrackingEnabled = Boolean(getProjectById(projectId)?.is_time_tracking_enabled);
  const { totalDuration } = useWorklogs(workspaceSlug, projectId, issueId, isTimeTrackingEnabled && canViewWorklogs);

  if (!isTimeTrackingEnabled || !canViewWorklogs) return <></>;

  return (
    <>
      <SidebarPropertyListItem icon={Timer} label={t("time_tracking")}>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="flex h-7.5 items-center rounded px-2 text-body-xs-regular text-secondary hover:bg-layer-1"
        >
          {totalDuration > 0 ? formatWorklogDuration(totalDuration) : disabled ? "—" : "Log time"}
        </button>
      </SidebarPropertyListItem>
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
