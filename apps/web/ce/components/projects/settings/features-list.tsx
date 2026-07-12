/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): wraps the core features list and appends the fork's
// Epics and Time tracking toggles. Epics enablement is not a Project
// boolean — it is derived from the epic ProjectIssueType link, managed via
// the epic-settings endpoint. Time tracking is the Project's
// is_time_tracking_enabled flag, updated through the regular project API.

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
// icons
import { Layers, Timer } from "lucide-react";
// plane imports
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { ToggleSwitch } from "@plane/ui";
// components
import { ProjectFeaturesList as CoreProjectFeaturesList } from "@/components/project/settings/features-list";
import { SettingsBoxedControlItem } from "@/components/settings/boxed-control-item";
// hooks
import { useProject } from "@/hooks/store/use-project";
// plane web
import { epicService } from "@/plane-web/services/epic.service";

type Props = {
  workspaceSlug: string;
  projectId: string;
  isAdmin: boolean;
};

const EpicsFeatureToggle = observer(function EpicsFeatureToggle(props: Props) {
  const { workspaceSlug, projectId, isAdmin } = props;
  // state
  const [isSubmitting, setIsSubmitting] = useState(false);
  // fetch current state
  const { data, mutate } = useSWR(
    workspaceSlug && projectId ? `EPIC_SETTINGS_${workspaceSlug}_${projectId}` : null,
    () => epicService.getSettings(workspaceSlug, projectId),
    { revalidateOnFocus: false }
  );

  const handleToggle = async () => {
    if (!isAdmin || isSubmitting || !data) return;
    setIsSubmitting(true);
    const next = !data.is_epic_enabled;
    try {
      await epicService.updateSettings(workspaceSlug, projectId, { is_epic_enabled: next });
      await mutate();
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Success!",
        message: `Epics ${next ? "enabled" : "disabled"} for this project.`,
      });
    } catch (error) {
      console.error(error);
      setToast({ type: TOAST_TYPE.ERROR, title: "Error!", message: "Failed to update the epics setting." });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-4">
      <SettingsBoxedControlItem
        title={
          <span className="flex items-center gap-2">
            <Layers className="h-5 w-5 flex-shrink-0 text-tertiary" />
            Epics
          </span>
        }
        description="Group large bodies of work spanning multiple cycles into epics and track their progress."
        control={
          <ToggleSwitch
            value={Boolean(data?.is_epic_enabled)}
            onChange={handleToggle}
            disabled={!isAdmin || isSubmitting || !data}
            size="sm"
          />
        }
      />
    </div>
  );
});

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
      <EpicsFeatureToggle {...props} />
      <TimeTrackingFeatureToggle {...props} />
    </>
  );
});
