/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Dialog } from "@headlessui/react";
import { ExternalLink, FileCode2, X } from "lucide-react";
import { observer } from "mobx-react";
import { DOCUMENTATION_URL, SOURCE_CODE_URL } from "@plane/constants";
// helpers
import { showExternalLinks } from "@/helpers/external-links";
import { getButtonStyling } from "@plane/propel/button";
import { HangarLogo } from "@plane/propel/icons";
import { IconButton } from "@plane/propel/icon-button";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { cn } from "@plane/utils";
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
    <ModalCore
      isOpen={isOpen}
      handleClose={handleClose}
      position={EModalPosition.CENTER}
      width={EModalWidth.XXXL}
      className="overflow-hidden"
    >
      {/* The identity is the point of this dialog, so it gets the room: the
          mark at a size that reads, the name at heading weight, and the build
          it is running underneath in a face that makes a version look like a
          version. */}
      <div className="border-b border-subtle bg-layer-1 px-6 py-6 sm:px-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-4">
            <div className="grid size-14 shrink-0 place-items-center rounded-xl border border-subtle bg-surface-1 shadow-raised-100">
              <HangarLogo className="h-9 w-auto text-primary" />
            </div>
            <div className="min-w-0">
              <Dialog.Title as="h2" className="truncate text-20 leading-7 font-semibold text-primary">
                {HANGAR_EDITION_NAME}
              </Dialog.Title>
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
            size="base"
            icon={X}
            aria-label={`Close ${HANGAR_EDITION_NAME} information`}
            onClick={handleClose}
          />
        </div>
      </div>

      <div className="max-h-[calc(100vh-8rem)] overflow-y-auto px-6 py-7 sm:px-8">
        <Dialog.Description className="max-w-xl text-14 leading-6 text-secondary">
          {content.description}
        </Dialog.Description>

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

        <div className="mt-7 flex flex-col gap-2 sm:flex-row">
          {/* AGPL-3.0 section 13 requires the source offer of anyone running a
              modified version over a network, so it is not gated. Documentation
              lives on a host this instance does not run, so it is. */}
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(getButtonStyling("secondary", "base"), "justify-center gap-2")}
          >
            <FileCode2 className="size-4" aria-hidden="true" />
            View source and license
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
          {linksAllowed && (
            <a
              href={documentationUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(getButtonStyling("tertiary", "base"), "justify-center gap-2")}
            >
              Documentation
              <ExternalLink className="size-3.5" aria-hidden="true" />
            </a>
          )}
        </div>

        <div className="mt-7 border-t border-subtle pt-5">
          <p className="text-11 leading-5 text-tertiary">{content.attribution}</p>
        </div>
      </div>
    </ModalCore>
  );
});
