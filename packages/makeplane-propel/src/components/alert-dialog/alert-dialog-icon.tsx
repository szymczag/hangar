import type * as React from "react";

import {
  AlertDialogIcon as AlertDialogIconElement,
  type AlertDialogIconProps as AlertDialogIconElementProps,
  type AlertDialogIconVariant,
} from "../../elements/alert-dialog/alert-dialog-icon";
import { InfoOutline } from "../../icons/miscellaneous/info-outline";
import { TickCircleOutline } from "../../icons/miscellaneous/tick-circle-outline";
import { WarningTriangleOutline } from "../../icons/miscellaneous/warning-triangle-outline";

export type { AlertDialogIconVariant } from "../../elements/alert-dialog/alert-dialog-icon";

type StatusGlyph = React.ComponentType<React.SVGProps<SVGSVGElement>>;

// Reuse the generated Plane outline glyphs shown by the updated Figma Alert Dialog family.
// The 16px source artwork scales to the specified 20px slot; no local SVG is authored here.
const STATUS_ICON: Record<AlertDialogIconVariant, StatusGlyph> = {
  danger: WarningTriangleOutline,
  warning: WarningTriangleOutline,
  info: InfoOutline,
  success: TickCircleOutline,
};

export type AlertDialogIconProps = Omit<AlertDialogIconElementProps, "children">;

/**
 * The leading intent badge above the title. Soft tinted surface + outline status glyph selected
 * from `variant` — callers never pass an icon (matches the Alert Dialog Figma family). Decorative
 * (`aria-hidden`) — the title carries the accessible name.
 *
 * `variant` is required (`danger` | `warning` | `info` | `success`).
 */
export function AlertDialogIcon({ variant, ...props }: AlertDialogIconProps) {
  const Glyph = STATUS_ICON[variant];
  return (
    <AlertDialogIconElement variant={variant} {...props}>
      <Glyph />
    </AlertDialogIconElement>
  );
}
