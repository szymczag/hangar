import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { pillVariants, type PillVariantProps } from "./variants";

export type { PillVariant, PillSize } from "./variants";

export type PillProps = Omit<useRender.ComponentProps<"button">, "className" | "style"> &
  PillVariantProps & {
    /**
     * Marks a trigger with no value yet. Sets `data-placeholder`, which dims the label and any
     * inherited-tint glyph to the placeholder colour — still dim while the picker is open; the
     * disabled and busy colours win over it.
     *
     * @default false
     */
    placeholder?: boolean;
  };

/**
 * The pill-shaped button container: a styled `<button>` with no baked content. Compose a
 * `PillLabel` and optional leading/trailing `Icon`, `Swatch` or avatar stack (or `Spinner` while
 * busy) inside it. Base-UI-agnostic — graft the Base UI `Button` behavior in `components` via
 * `<BaseButton render={<Pill/>} />`; an open picker shows through Base UI's `data-popup-open` when
 * a `Menu`/`Popover` trigger is grafted the same way.
 */
export function Pill({ size, variant, placeholder = false, render, ...props }: PillProps) {
  // A boolean capability reflected as the attribute the cva keys off. Intersected onto
  // ElementProps because this repo's React DOM typings don't admit arbitrary `data-*` keys on the
  // annotated object (see `DisclosureIndicator`).
  const defaultProps: useRender.ElementProps<"button"> & { "data-placeholder"?: string } = {
    className: pillVariants({ size, variant }),
    type: "button",
    "data-placeholder": placeholder ? "" : undefined,
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
