/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
import { useTheme } from "next-themes";
// plane imports
import { Button } from "@makeplane/propel/components/button";
import { Button as ButtonElement } from "@makeplane/propel/elements/button";
import { DOCUMENTATION_URL } from "@plane/constants";
// assets
import ProjectDarkEmptyState from "@/app/assets/empty-state/project-settings/no-projects-dark.png?url";
import ProjectLightEmptyState from "@/app/assets/empty-state/project-settings/no-projects-light.png?url";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
// hooks
import { useCommandPalette } from "@/hooks/store/use-command-palette";
import { useInstance } from "@/hooks/store/use-instance";

function ProjectSettingsPage() {
  // store hooks
  const { resolvedTheme } = useTheme();
  const { toggleCreateProjectModal } = useCommandPalette();
  const { config } = useInstance();
  // derived values
  const resolvedPath = resolvedTheme === "dark" ? ProjectDarkEmptyState : ProjectLightEmptyState;
  return (
    <div className="mx-auto flex h-full max-w-[480px] flex-col items-center justify-center gap-4">
      <img src={resolvedPath} alt="No projects yet" />
      <div className="text-body-md-semibold text-tertiary">No projects yet</div>
      <div className="text-center text-body-xs-regular text-tertiary">
        Projects act as the foundation for goal-driven work. They let you manage your teams, tasks, and everything you
        need to get things done.
      </div>
      <div className="flex gap-2">
        {/* Fork: the operator's documentation, and only where outbound links are allowed. */}
        {showExternalLinks(config) && (
          <ButtonElement
            variant="secondary"
            size="sm"
            stretch="auto"
            render={
              <Link
                href={config?.product?.documentation_url ?? DOCUMENTATION_URL}
                target="_blank"
                rel="noopener noreferrer"
              />
            }
          >
            Learn more about projects
          </ButtonElement>
        )}
        <Button
          variant="primary"
          size="sm"
          stretch="auto"
          label="Start your first project"
          onClick={() => toggleCreateProjectModal(true)}
        />
      </div>
    </div>
  );
}

export default observer(ProjectSettingsPage);
