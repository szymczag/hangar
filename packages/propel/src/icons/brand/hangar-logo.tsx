/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import * as React from "react";

import type { ISvgIcons } from "../type";

/**
 * Hangar's compact mark: a shelter framing three stacked work layers.
 *
 * The mark deliberately uses currentColor so it stays legible in every
 * application theme and at favicon-sized resolutions.
 */
export function HangarMark({ className, ...props }: ISvgIcons) {
  return (
    <svg
      viewBox="0 0 52 52"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
      {...props}
    >
      <path d="M5 45V18.5L26 5l21 13.5V45h-6V21.8L26 12.2 11 21.8V45H5Z" fill="currentColor" />
      <path d="m15 26 11-6 11 6v6l-11-4.2L15 32v-6Z" fill="currentColor" opacity="0.46" />
      <path d="m15 34 11-4 11 4v5l-11-2.5L15 39v-5Z" fill="currentColor" opacity="0.7" />
      <path d="m15 41 11-2.5L37 41v4H15v-4Z" fill="currentColor" />
    </svg>
  );
}

export function HangarLogo({ className, ...props }: ISvgIcons) {
  return (
    <svg
      viewBox="0 0 182 52"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Hangar"
      {...props}
    >
      <g>
        <path d="M3 45V18.5L24 5l21 13.5V45h-6V21.8L24 12.2 9 21.8V45H3Z" fill="currentColor" />
        <path d="m13 26 11-6 11 6v6l-11-4.2L13 32v-6Z" fill="currentColor" opacity="0.46" />
        <path d="m13 34 11-4 11 4v5l-11-2.5L13 39v-5Z" fill="currentColor" opacity="0.7" />
        <path d="m13 41 11-2.5L35 41v4H13v-4Z" fill="currentColor" />
      </g>
      <text
        x="56"
        y="37"
        fill="currentColor"
        fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
        fontSize="34"
        fontWeight="600"
        letterSpacing="-1.5"
      >
        Hangar
      </text>
    </svg>
  );
}
