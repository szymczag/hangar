import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, cx, type VariantProps } from "class-variance-authority";

import { nodeSlotClass } from "./node-slot";
import { type StrictVariantProps } from "./variant-props";

/**
 * The shared decorative glyph slot (rule 4a): an `aria-hidden` `<span>` that sizes its single svg
 * child to the inherited `--node-size`. Before this, seventeen families each kept a byte-identical
 * `<Family>Icon` part differing only in tint or a local node size — those are gone; `components`
 * ready-mades and stories compose this one. A family keeps its OWN icon part only when its styling
 * is genuinely distinct (toast/banner/alert-dialog variants, navigation-menu's Base-UI-named
 * rotating `Icon`).
 *
 * Both axes carry a real default (`inherit` — rule 12's sanctioned mechanism): an icon slot's size
 * and color normally come from its container's `--node-size` and `currentColor`. The explicit steps
 * are the ladder's rung labels and read its tokens, so pinning one can only ever agree with a
 * control at the same label — it cannot invent a third glyph scale the way a private one could.
 */
const iconDefaultVariants = {
  tint: "inherit",
  size: "inherit",
} as const;

export const iconVariants = cva(nodeSlotClass, {
  variants: {
    tint: {
      inherit: "",
      danger: "text-danger-primary",
      // `placeholder` is the input-adornment tint: muted at rest, brightening when the enclosing
      // `/control` group is focused (autocomplete/combobox search icons), and dimming when that
      // group's control is disabled. `muted` is the plain static form — same resting color, no
      // focus/disabled behavior — for non-interactive slots like an avatar's anonymous glyph.
      // `secondary` gets the same disabled dimming (it's the tint the shipped Input icon demo
      // actually uses) but not the focus brightening, which stays `placeholder`'s alone.
      placeholder: cx(
        "text-icon-placeholder transition-colors",
        "group-focus-within/control:text-icon-secondary",
        "group-has-[:disabled]/control:text-icon-disabled group-data-disabled/control:text-icon-disabled",
      ),
      muted: "text-icon-placeholder",
      secondary: cx(
        "text-icon-secondary",
        "group-has-[:disabled]/control:text-icon-disabled group-data-disabled/control:text-icon-disabled",
      ),
      tertiary: "text-icon-tertiary",
    },
    // The ladder's rungs, not a private scale. `size="md"` inside a `size="md"` control is the
    // same glyph the control would have set itself, so the two can no longer disagree — which is
    // the whole reason the axis exists. `inherit` stays the default and the normal case: a glyph
    // in a rung-declaring container needs no size at all.
    size: {
      inherit: "",
      xs: "[--node-size:var(--control-glyph-xs)]",
      sm: "[--node-size:var(--control-glyph-sm)]",
      md: "[--node-size:var(--control-glyph-md)]",
      lg: "[--node-size:var(--control-glyph-lg)]",
      xl: "[--node-size:var(--control-glyph-xl)]",
      "2xl": "[--node-size:var(--control-glyph-2xl)]",
    },
  },
  defaultVariants: iconDefaultVariants,
});

type IconVariantConfig = VariantProps<typeof iconVariants>;
export type IconTint = NonNullable<IconVariantConfig["tint"]>;
export type IconSize = NonNullable<IconVariantConfig["size"]>;

export type IconVariantProps = StrictVariantProps<
  typeof iconVariants,
  keyof typeof iconDefaultVariants
>;

export type IconProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> &
  IconVariantProps;

export function Icon({ tint, size, render, ...props }: IconProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    "aria-hidden": true,
    className: iconVariants({ tint, size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
