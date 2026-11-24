/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import * as React from "react";

import type { ISvgIcons } from "../type";

/** Hangar's canonical compact mark. */
export function HangarMark({ className, ...props }: ISvgIcons) {
  return (
    <svg
      viewBox="0 0 305 258"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      <image href="/hangar-mark.png" width="305" height="258" preserveAspectRatio="xMidYMid meet" />
    </svg>
  );
}

/**
 * The wordmark's letters and roof are white, drawn for a dark surface. On a
 * light theme surface they vanish, so `themed` inverts the artwork there: the
 * letters turn near-black and the hue rotation keeps the chevrons blue. Dark
 * themes show the artwork as drawn. Leave it off where the logo sits on a fixed
 * dark or accent background.
 */
const HANGAR_LOGO_THEMED_CLASSNAME = "invert hue-rotate-180 dark:invert-0 dark:hue-rotate-0";

type HangarLogoProps = ISvgIcons & {
  /** Adapt the wordmark to the theme's surface (see HANGAR_LOGO_THEMED_CLASSNAME). */
  themed?: boolean;
};

/** Hangar's canonical wordmark, preserving the original letter artwork. */
export function HangarLogo({ className, themed = false, ...props }: HangarLogoProps) {
  return (
    <svg
      viewBox="0 0 868 258"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={[themed ? HANGAR_LOGO_THEMED_CLASSNAME : undefined, className].filter(Boolean).join(" ") || undefined}
      role="img"
      aria-label="Hangar"
      focusable="false"
      {...props}
    >
      <image href="/hangar-wordmark.png" width="868" height="258" preserveAspectRatio="xMidYMid meet" />
    </svg>
  );
}
