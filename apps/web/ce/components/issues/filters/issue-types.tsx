/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): filter work items by their custom type.

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// icons
import { Shapes } from "lucide-react";
// components
import { FilterHeader, FilterOption } from "@/components/issues/issue-layouts/filters";
// plane web
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";

type Props = {
  appliedFilters: string[] | null;
  handleUpdate: (val: string) => void;
  searchQuery: string;
};

export const FilterIssueTypes = observer(function FilterIssueTypes(props: Props) {
  const { appliedFilters, handleUpdate, searchQuery } = props;
  // state
  const [previewEnabled, setPreviewEnabled] = useState(true);
  // router
  const { workspaceSlug, projectId } = useParams();
  // data
  const { issueTypes } = useIssueTypes(workspaceSlug?.toString(), projectId?.toString());
  // derived values
  const availableTypes = (issueTypes ?? []).filter((type) => !type.is_epic && type.is_active);
  const filteredTypes = availableTypes.filter((type) => type.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const appliedFilterIds = new Set(appliedFilters ?? []);
  const appliedFiltersCount = appliedFilters?.length ?? 0;

  if (availableTypes.length === 0) return null;

  return (
    <>
      <FilterHeader
        title={`Work item type${appliedFiltersCount > 0 ? ` (${appliedFiltersCount})` : ""}`}
        isPreviewEnabled={previewEnabled}
        handleIsPreviewEnabled={() => setPreviewEnabled(!previewEnabled)}
      />
      {previewEnabled && (
        <div>
          {filteredTypes.length > 0 ? (
            filteredTypes.map((type) => (
              <FilterOption
                key={type.id}
                isChecked={appliedFilterIds.has(type.id)}
                onClick={() => handleUpdate(type.id)}
                icon={<Shapes className="h-3 w-3 text-tertiary" />}
                title={type.name}
              />
            ))
          ) : (
            <p className="text-11 text-tertiary italic">No matches found</p>
          )}
        </div>
      )}
    </>
  );
});
