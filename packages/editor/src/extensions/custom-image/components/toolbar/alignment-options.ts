/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AlignCenter, AlignLeft, AlignRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
// local imports
import type { TCustomImageAlignment } from "../../types";

// The toolbar's alignment choices and their icons. They sit with the toolbar,
// not in `custom-image/utils.ts`, which the image node's schema config imports
// and live loads through the server codecs.
export const IMAGE_ALIGNMENT_OPTIONS: {
  label: string;
  value: TCustomImageAlignment;
  icon: LucideIcon;
}[] = [
  {
    label: "Left",
    value: "left",
    icon: AlignLeft,
  },
  {
    label: "Center",
    value: "center",
    icon: AlignCenter,
  },
  {
    label: "Right",
    value: "right",
    icon: AlignRight,
  },
];
