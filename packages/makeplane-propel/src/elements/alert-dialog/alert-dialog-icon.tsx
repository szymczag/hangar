import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type AlertDialogIconVariantProps, alertDialogIconVariants } from "./variants";

export type { AlertDialogIconVariant } from "./variants";

export type AlertDialogIconProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> &
  AlertDialogIconVariantProps;

/**
 * The leading intent badge above the title. Soft tinted surface + 20px glyph (caller passes the
 * icon child; the `components` ready-made supplies an outline glyph from `variant`). Decorative —
 * the title carries the accessible name — so it is `aria-hidden`.
 *
 * `variant` is required and sets the badge fill + glyph tint (`danger` | `warning` | `info` |
 * `success`).
 */
export function AlertDialogIcon({ variant, render, ...props }: AlertDialogIconProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: alertDialogIconVariants({ variant }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
