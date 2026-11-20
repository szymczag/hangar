import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva } from "class-variance-authority";

import { type StrictVariantProps } from "./variant-props";

const positionerDefaultVariants = {
  hideWhenAnchorHidden: false,
} as const;

/**
 * The shared overlay positioner surface, grafted onto any Base UI `*.Positioner` behavior in
 * `components` (`<BaseMenu.Positioner render={<Positioner />}>`). Floats the anchored overlay above
 * page content and drops the focus ring. Byte-identical across every overlay family, so it lives
 * here rather than being copied per family (rule 4a).
 *
 * Opt into `hideWhenAnchorHidden` for overlays that should vanish when Base UI marks the anchor
 * clipped/out of view (`data-anchor-hidden`) — Tooltip needs this so the tip does not linger after
 * the trigger scrolls away. Left off for menus/popovers: context-menu virtual anchors can carry
 * that attribute while the menu is still open, and `invisible` would hide accessible roles.
 */
export const positionerVariants = cva("z-50 outline-none", {
  variants: {
    hideWhenAnchorHidden: {
      true: "data-anchor-hidden:invisible",
      false: null,
    },
  },
  defaultVariants: positionerDefaultVariants,
});

export type PositionerVariantProps = StrictVariantProps<
  typeof positionerVariants,
  keyof typeof positionerDefaultVariants
>;

export type PositionerProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  PositionerVariantProps;

export function Positioner({ render, hideWhenAnchorHidden, ...props }: PositionerProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: positionerVariants({ hideWhenAnchorHidden }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
