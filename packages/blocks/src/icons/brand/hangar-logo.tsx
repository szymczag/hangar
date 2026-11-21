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

/** Hangar's canonical wordmark, preserving the original letter artwork. */
export function HangarLogo({ className, ...props }: ISvgIcons) {
  return (
    <svg
      viewBox="0 0 868 258"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Hangar"
      focusable="false"
      {...props}
    >
      <image href="/hangar-wordmark.png" width="868" height="258" preserveAspectRatio="xMidYMid meet" />
    </svg>
  );
}
