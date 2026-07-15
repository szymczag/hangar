/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): wraps the core features list and appends the fork's
// Time tracking toggle. Epic is a work item type configured under Work item
// types, not a separately enabled project feature.

import { useState } from "react";
import { observer } from "mobx-react";
// icons
import { Timer } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { ToggleSwitch } from "@plane/ui";
// components
import { ProjectFeaturesList as CoreProjectFeaturesList } from "@/components/project/settings/features-list";
import { SettingsBoxedControlItem } from "@/components/settings/boxed-control-item";
// hooks
import { useProject } from "@/hooks/store/use-project";

type Props = {
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
};

const TimeTrackingFeatureToggle = observer(function TimeTrackingFeatureToggle(props: Props) {
  const { workspaceSlug, projectId, isAdmin } = props;
  // i18n
  const { t } = useTranslation();
  // state
  const [isSubmitting, setIsSubmitting] = useState(false);
  // store hooks
  const { getProjectById, updateProject } = useProject();
  // derived values
  const project = getProjectById(projectId);

  const handleToggle = async () => {
    if (!isAdmin || isSubmitting || !project) return;
    setIsSubmitting(true);
    const next = !project.is_time_tracking_enabled;
    try {
      await updateProject(workspaceSlug, projectId, { is_time_tracking_enabled: next });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Success!",
        message: `Time tracking ${next ? "enabled" : "disabled"} for this project.`,
      });
    } catch (error) {
      console.error(error);
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to update the time tracking setting." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-4">
      <SettingsBoxedControlItem
        title={
          <span className="flex items-center gap-2">
            <Timer className="h-5 w-5 flex-shrink-0 text-tertiary" />
            {t("project_settings.features.time_tracking.title")}
          </span>
        }
        description={t("project_settings.features.time_tracking.description")}
        control={
          <ToggleSwitch
            value={Boolean(project?.is_time_tracking_enabled)}
            onChange={handleToggle}
            disabled={!isAdmin || isSubmitting || !project}
            size="sm"
          />
        }
      />
    </div>
  );
});

export const ProjectFeaturesList = observer(function ProjectFeaturesList(props: Props) {
  return (
    <>
      <CoreProjectFeaturesList {...props} />
      <TimeTrackingFeatureToggle {...props} />
    </>
  );
});
