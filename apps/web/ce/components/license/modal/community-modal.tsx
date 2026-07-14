/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Dialog } from "@headlessui/react";
import { BookOpen, Check, ExternalLink, FileCode2, X } from "lucide-react";
import { observer } from "mobx-react";
import { DOCUMENTATION_URL, SOURCE_CODE_URL } from "@plane/constants";
import { getButtonStyling } from "@plane/propel/button";
import { HangarLogo } from "@plane/propel/icons";
import { IconButton } from "@plane/propel/icon-button";
import { EModalPosition, EModalWidth, ModalCore } from "@plane/ui";
import { cn } from "@plane/utils";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import packageJson from "package.json";
// content
import content from "./community-modal-content.json";

export type HangarCommunityModalProps = {
  isOpen: boolean;
  handleClose: () => void;
};

export const HangarCommunityModal = observer(function HangarCommunityModal(props: HangarCommunityModalProps) {
  const { isOpen, handleClose } = props;
  const { config } = useInstance();

  const documentationUrl = config?.product?.documentation_url ?? DOCUMENTATION_URL;
  const sourceUrl = config?.product?.source_url ?? SOURCE_CODE_URL;
  const version = config?.product?.version ?? packageJson.version;
  const releaseNotesUrl = `${sourceUrl.replace(/\/$/, "")}/releases`;

  return (
    <ModalCore
      isOpen={isOpen}
      handleClose={handleClose}
      position={EModalPosition.CENTER}
      width={EModalWidth.XXXL}
      className="overflow-hidden"
    >
      <div className="border-b border-subtle bg-layer-1 px-6 py-5 sm:px-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg border border-subtle bg-surface-1 shadow-raised-100">
              <HangarLogo className="h-6 w-auto text-primary" />
            </div>
            <div className="min-w-0">
              <p className="text-11 font-semibold tracking-[0.12em] text-secondary uppercase">Hangar Community</p>
              <p className="truncate text-13 text-tertiary">Version {version}</p>
            </div>
          </div>
          <IconButton
            variant="ghost"
            size="base"
            icon={X}
            aria-label="Close Hangar Community information"
            onClick={handleClose}
          />
        </div>
      </div>

      <div className="max-h-[calc(100vh-8rem)] overflow-y-auto px-6 py-7 sm:px-8 sm:py-8">
        <div className="max-w-2xl">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent-strong/20 bg-accent-primary/10 px-3 py-1 text-11 font-semibold tracking-wide text-accent-primary uppercase">
            <span className="size-1.5 rounded-full bg-accent-primary" aria-hidden="true" />
            {content.eyebrow}
          </div>
          <Dialog.Title as="h2" className="text-24 leading-8 font-semibold text-primary">
            {content.title}
          </Dialog.Title>
          <Dialog.Description className="mt-3 max-w-xl text-14 leading-6 text-secondary">
            {content.description}
          </Dialog.Description>
        </div>

        <section className="mt-7" aria-labelledby="hangar-community-features">
          <h3 id="hangar-community-features" className="text-13 font-semibold text-primary">
            {content.featuresHeading}
          </h3>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {content.features.map((feature) => (
              <li
                key={feature}
                className="flex min-h-11 items-center gap-3 rounded-lg border border-subtle bg-surface-2 px-3.5 py-2.5 text-13 font-medium text-primary"
              >
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-success-subtle text-success-primary">
                  <Check className="size-3.5" strokeWidth={2.5} aria-hidden="true" />
                </span>
                {feature}
              </li>
            ))}
          </ul>
          <p className="mt-3 text-12 leading-5 text-tertiary">{content.availabilityNote}</p>
        </section>

        <div className="mt-7 flex flex-col gap-2 sm:flex-row">
          <a
            href={releaseNotesUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(getButtonStyling("primary", "base"), "justify-center gap-2")}
          >
            <BookOpen className="size-4" aria-hidden="true" />
            View release notes
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
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
          <a
            href={documentationUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(getButtonStyling("tertiary", "base"), "justify-center gap-2")}
          >
            Documentation
            <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        </div>

        <div className="mt-7 border-t border-subtle pt-5">
          <p className="text-11 leading-5 text-tertiary">{content.attribution}</p>
        </div>
      </div>
    </ModalCore>
  );
});
