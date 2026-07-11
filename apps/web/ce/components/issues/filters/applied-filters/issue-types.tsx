/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Fork (see FORK.md): applied work-item-type filter chips.

import { observer } from "mobx-react";
import { useParams } from "next/navigation";
// icons
import { Shapes } from "lucide-react";
import { CloseIcon } from "@plane/propel/icons";
// plane web
import { useIssueTypes } from "@/plane-web/hooks/use-issue-types";

type Props = {
  handleRemove: (val: string) => void;
  values: string[];
  editable: boolean | undefined;
};

export const AppliedIssueTypeFilters = observer(function AppliedIssueTypeFilters(props: Props) {
  const { handleRemove, values, editable } = props;
  // router
  const { workspaceSlug, projectId } = useParams();
  // data
  const { getTypeById } = useIssueTypes(workspaceSlug?.toString(), projectId?.toString());

  return (
    <>
      {values.map((typeId) => {
        const typeDetails = getTypeById(typeId);
        if (!typeDetails) return null;
        return (
          <div key={typeId} className="flex items-center gap-1 rounded-sm bg-layer-1 p-1 text-11">
            <Shapes className="h-3 w-3 text-tertiary" />
            {typeDetails.name}
            {editable && (
              <button
                type="button"
                className="grid place-items-center text-tertiary hover:text-secondary"
                onClick={() => handleRemove(typeId)}
              >
                <CloseIcon height={10} width={10} strokeWidth={2} />
              </button>
            )}
          </div>
        );
      })}
    </>
  );
});
