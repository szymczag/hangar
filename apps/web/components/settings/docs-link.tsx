/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { AnchorButton } from "@makeplane/propel/components/anchor-button";
import { useTranslation } from "@plane/i18n";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
// hooks
import { useInstance } from "@/hooks/store/use-instance";

type Props = {
  href: string;
};

/** A compact "Docs" link that opens the matching help-center page in a new tab. */
// Fork: rendered only where the operator allows outbound links (see FORK.md).
export const SettingsDocsLink = observer(function SettingsDocsLink({ href }: Props) {
  const { t } = useTranslation();
  const { config } = useInstance();

  if (!href || !showExternalLinks(config)) return null;

  return (
    <span className="ms-1 inline-flex align-middle">
      <AnchorButton variant="secondary" size="xs" href={href} external label={t("docs")} />
    </span>
  );
});
