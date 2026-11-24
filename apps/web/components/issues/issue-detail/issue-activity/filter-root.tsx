/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import type { TActivityFilters, TActivityFilterOption } from "@plane/constants";
import { ACTIVITY_FILTER_TYPE_OPTIONS, EActivityFilterType } from "@plane/constants";
// components
import { ActivityFilter } from "@/components/issues/issue-detail/issue-activity";
// hooks
import { useProject } from "@/hooks/store/use-project";

export type TActivityFilterRoot = {
  selectedFilters: TActivityFilters[];
  toggleFilter: (filter: TActivityFilters) => void;
  projectId: string;
  isIntakeIssue?: boolean;
  canViewWorklogs: boolean;
  /** Restricts the options to these filters (e.g. the ones the active activity tab covers). */
  filterKeys?: TActivityFilters[];
};

export const ActivityFilterRoot = observer(function ActivityFilterRoot(props: TActivityFilterRoot) {
  const { selectedFilters, toggleFilter, projectId, isIntakeIssue = false, canViewWorklogs, filterKeys } = props;
  // store hooks
  const { getProjectById } = useProject();
  // derived values — the worklog filter only applies where worklogs can exist
  const isTimeTrackingEnabled = Boolean(getProjectById(projectId)?.is_time_tracking_enabled);
  const showWorklogFilter = isTimeTrackingEnabled && canViewWorklogs && !isIntakeIssue;
  const selectedFilterSet = new Set(selectedFilters);
  const allowedFilterSet = filterKeys ? new Set(filterKeys) : undefined;

  const filters = Object.entries(ACTIVITY_FILTER_TYPE_OPTIONS).reduce<TActivityFilterOption[]>(
    (options, [key, value]) => {
      const filterKey = key as TActivityFilters;
      if (allowedFilterSet && !allowedFilterSet.has(filterKey)) return options;
      if (!showWorklogFilter && filterKey === EActivityFilterType.WORKLOG) return options;
      options.push({
        key: filterKey,
        labelTranslationKey: value.labelTranslationKey,
        isSelected: selectedFilterSet.has(filterKey),
        onClick: () => toggleFilter(filterKey),
      });
      return options;
    },
    []
  );

  return <ActivityFilter selectedFilters={selectedFilters} filterOptions={filters} />;
});
