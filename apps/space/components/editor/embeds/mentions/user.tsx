/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// helpers
import { cn } from "@plane/utils";
// hooks
import { useUser } from "@/hooks/store/use-user";

type Props = {
  id: string;
};

/**
 * A user mention on a published board. The board does not say whom a mention names:
 * resolving the id would need the project's member list, which a board readable by
 * anyone with the link does not publish (FORK.md, S30). Only the viewer's own mention
 * shows a name, their own.
 */
export const EditorUserMention = observer(function EditorUserMention(props: Props) {
  const { id } = props;
  // store hooks
  const { data: currentUser } = useUser();
  // derived values
  const isCurrentUser = !!currentUser?.id && id === currentUser.id;
  const label = (isCurrentUser && currentUser?.display_name) || "user";

  return (
    <div
      className={cn("not-prose inline rounded-sm bg-accent-primary/20 px-1 py-0.5 text-accent-primary no-underline", {
        "bg-yellow-500/20 text-yellow-500": isCurrentUser,
      })}
    >
      @{label}
    </div>
  );
});
