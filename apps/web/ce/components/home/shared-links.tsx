/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { EyeOff, Link2, RotateCcw } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// hooks
import { useWorkspaceSharedLinks } from "@/plane-web/hooks/use-workspace-shared-links";

type Props = {
  workspaceSlug: string;
};

/**
 * The quick links a workspace admin gives everyone.
 *
 * Rendered as its own group above the personal ones, because they are not the
 * reader's to edit -- the only thing they may do is take one off their own home
 * page, and put it back. With no shared links this renders nothing and the
 * widget looks exactly as it did before.
 */
export const WorkspaceSharedLinks = ({ workspaceSlug }: Props) => {
  const { visibleLinks, hiddenLinks, setHidden, isLoading } = useWorkspaceSharedLinks(workspaceSlug);
  const [showingHidden, setShowingHidden] = useState(false);
  const { t } = useTranslation();

  if (isLoading || (visibleLinks.length === 0 && hiddenLinks.length === 0)) return null;

  const shown = showingHidden ? [...visibleLinks, ...hiddenLinks] : visibleLinks;

  return (
    <div className="mb-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="text-13 font-semibold text-tertiary">
          {t("workspace_settings.settings.home_defaults.shared_links")}
        </span>
        {hiddenLinks.length > 0 && (
          <button
            type="button"
            onClick={() => setShowingHidden((current) => !current)}
            className="text-12 font-medium text-accent-primary"
          >
            {showingHidden
              ? t("common.cancel")
              : `${t("workspace_settings.settings.home_defaults.show_hidden")} (${hiddenLinks.length})`}
          </button>
        )}
      </div>

      <ul className="flex w-full flex-wrap gap-2">
        {shown.map((link) => (
          <li key={link.id} className="group/shared-link">
            <span
              className={cn(
                "flex items-center gap-2 rounded-md border border-subtle bg-surface-1 px-3 py-2 transition-colors",
                link.is_hidden && "opacity-60"
              )}
            >
              <Link2 className="size-4 shrink-0 text-tertiary" aria-hidden="true" />
              <a
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="max-w-56 truncate text-13 text-primary hover:underline"
                title={link.url}
              >
                {link.title || link.url}
              </a>
              <button
                type="button"
                onClick={() => setHidden(link.id, !link.is_hidden)}
                aria-label={
                  link.is_hidden
                    ? `${t("workspace_settings.settings.home_defaults.show_hidden")}: ${link.title || link.url}`
                    : `${t("workspace_settings.settings.home_defaults.hide")}: ${link.title || link.url}`
                }
                className="rounded-sm p-0.5 text-tertiary opacity-0 transition-opacity group-hover/shared-link:opacity-100 hover:text-primary focus-visible:opacity-100"
              >
                {link.is_hidden ? (
                  <RotateCcw className="size-3.5" aria-hidden="true" />
                ) : (
                  <EyeOff className="size-3.5" aria-hidden="true" />
                )}
              </button>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
};
