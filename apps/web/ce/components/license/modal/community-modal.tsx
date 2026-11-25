/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { AnchorButton } from "@makeplane/propel/components/anchor-button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@makeplane/propel/components/dialog";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { CloseOutline } from "@makeplane/propel/icons";
import { HangarMark } from "@plane/blocks/icons";
import { DOCUMENTATION_URL, SOURCE_CODE_URL } from "@plane/constants";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import packageJson from "package.json";
// content
import { RELEASE_NOTES } from "../release-notes.generated";
import content from "./community-modal-content.json";

export const HANGAR_EDITION_NAME = "Hangar by @szymczag";

/** Compare versions ignoring the tag's leading `v`, which only one side carries. */
const sameVersion = (a: string, b: string): boolean =>
  a.replace(/^v/, "") === b.replace(/^v/, "") && a.replace(/^v/, "") !== "";

export type HangarCommunityModalProps = {
  isOpen: boolean;
  handleClose: () => void;
};

export const HangarCommunityModal = observer(function HangarCommunityModal(props: HangarCommunityModalProps) {
  const { isOpen, handleClose } = props;
  const { config } = useInstance();

  const documentationUrl = config?.product?.documentation_url ?? DOCUMENTATION_URL;
  const sourceUrl = config?.product?.source_url ?? SOURCE_CODE_URL;
  const linksAllowed = showExternalLinks(config);
  const version = config?.product?.version ?? packageJson.version;

  // The notes are bundled from the release file at build time, so they describe
  // a specific version. If this build is running a different one -- APP_VERSION
  // is an environment variable, and a dev build has none -- say nothing rather
  // than describe the previous release as though it were this one.
  //
  // The two sides spell the version differently and always have: the notes are
  // named `docs/releases/hangar-v<version>.md`, so the generator yields
  // "0.1.0-rc.41", while APP_VERSION carries the tag's leading `v`. Comparing
  // them raw made this gate permanently false, which silently turned the
  // highlights off in every build rather than in the mismatched ones.
  const highlights = sameVersion(RELEASE_NOTES.version, version) ? RELEASE_NOTES.highlights : [];
  const upstream = RELEASE_NOTES.upstream.version || packageJson.version;

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) handleClose();
      }}
    >
      <DialogContent size="lg">
        {/* The identity is the point of this dialog, so it gets the room: the
          mark at a size that reads, the name at heading weight, and the build
          it is running underneath in a face that makes a version look like a
          version. */}
        <div className="border-b border-subtle bg-layer-1 px-6 py-6 sm:px-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-center gap-4">
              <div className="grid size-14 shrink-0 place-items-center rounded-xl border border-subtle bg-surface-1 shadow-raised-100">
                {/* The mark, not the wordmark: this badge is a 56px square, and
                  the wordmark is 868x258, so at `h-9 w-auto` it rendered 119px
                  wide and spilled ~32px out of either side of its own box. */}
                <HangarMark className="h-9 w-auto text-primary" />
              </div>
              <div className="min-w-0">
                <DialogTitle>{HANGAR_EDITION_NAME}</DialogTitle>
                <p className="font-mono mt-1 truncate text-12 text-tertiary">
                  {version}
                  <span className="mx-2 text-placeholder" aria-hidden="true">
                    ·
                  </span>
                  {content.builtOnLabel} {upstream}
                  {RELEASE_NOTES.upstream.revision ? ` (${RELEASE_NOTES.upstream.revision})` : ""}
                </p>
              </div>
            </div>
            <IconButton
              variant="ghost"
              size="md"
              icon={<Icon icon={CloseOutline} />}
              aria-label={`Close ${HANGAR_EDITION_NAME} information`}
              onClick={handleClose}
            />
          </div>
        </div>

        <div className="max-h-[calc(100vh-8rem)] overflow-y-auto px-6 py-7 sm:px-8">
          <DialogDescription>{content.description}</DialogDescription>

          <section className="mt-7" aria-labelledby="hangar-release-notes">
            <h3 id="hangar-release-notes" className="text-13 font-semibold text-primary">
              {content.releaseNotesHeading}
            </h3>
            {highlights.length > 0 ? (
              // A rule per line rather than bullets or check marks: this is a
              // record of what changed, not a list of things you are getting.
              <ul className="mt-3 divide-y divide-subtle border-t border-subtle">
                {highlights.map((highlight) => (
                  <li key={highlight} className="py-2.5 text-13 leading-5 text-secondary">
                    {highlight}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-13 leading-5 text-tertiary">{content.releaseNotesUnavailable}</p>
            )}
          </section>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-5">
            {/* AGPL-3.0 section 13 requires the source offer of anyone running a
              modified version over a network, so it is not gated. Documentation
              lives on a host this instance does not run, so it is. */}
            <AnchorButton
              variant="primary"
              size="md"
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              external
              label="View source and license"
            />
            {linksAllowed && (
              <AnchorButton
                variant="primary"
                size="md"
                href={documentationUrl}
                target="_blank"
                rel="noopener noreferrer"
                external
                label="Documentation"
              />
            )}
          </div>

          <div className="mt-7 border-t border-subtle pt-5">
            <p className="text-11 leading-5 text-tertiary">{content.attribution}</p>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
});
