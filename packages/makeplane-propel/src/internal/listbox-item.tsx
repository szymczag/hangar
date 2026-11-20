import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, cx, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "./variant-props";

/**
 * The autocomplete family's option row, grafted onto Base UI's `Autocomplete.Item` behavior in
 * `components` (`<BaseAutocomplete.Item render={<ListboxItem size="lg" />} value={…} />`): a flush
 * flex row with highlight/disabled states and a size axis for height + text size. Autocomplete rows
 * carry no selection marker. (Select and Combobox rows use the shared menu-row chrome instead.)
 */
export const listboxItemVariants = cva(
  cx(
    // The icon-to-label gap ramps per rung (below). This REVERSES a decision taken one commit
    // earlier, which declined the same change on the grounds that these rows span four sizes while
    // the menu row does not — so a density question about every dropdown should not be settled in
    // passing. That was the right instinct and the wrong conclusion: spanning four sizes is what
    // makes a FLAT gap indefensible here, because the glyph already ramps and the ladder ties the
    // two together by an enforced invariant, so one flat value cannot be right at every step.
    // `px-2` and `rounded-sm` do stay flat, per the geometry token ramp entry in CHANGELOG.md — popup rows
    // do not ramp with their trigger. That rule still binds them; it does not bind the gap, which
    // is the only one of the three the ladder pairs to something that ramps.
    "flex cursor-default items-center rounded-sm px-2 text-primary outline-none",
    "data-highlighted:bg-layer-transparent-hover data-highlighted:text-primary",
    "data-disabled:cursor-not-allowed data-disabled:text-disabled",
  ),
  {
    variants: {
      // Figma "Size" axis: row heights with matching text sizes, on the ladder rungs. `lg`
      // reproduces the classic autocomplete row.
      // Each rung also declares its glyph: the row is the `--node-size` ancestor for any icon a
      // consumer puts in it, and the property does not fall back — an option row that declared no
      // glyph left `size-(--node-size)` resolving to an invalid value, so the svg took its
      // intrinsic size (24px) instead of the rung's.
      size: {
        md: "min-h-(--control-height-md) gap-(--control-gap-md) text-body-xs-regular [--node-size:var(--control-glyph-md)]",
        lg: "min-h-(--control-height-lg) gap-(--control-gap-lg) text-body-sm-regular [--node-size:var(--control-glyph-lg)]",
        xl: "min-h-(--control-height-xl) gap-(--control-gap-xl) text-body-sm-regular [--node-size:var(--control-glyph-xl)]",
        "2xl":
          "min-h-(--control-height-2xl) gap-(--control-gap-2xl) text-body-md-regular [--node-size:var(--control-glyph-2xl)]",
      },
    },
  },
);

export type ListboxItemSize = NonNullable<VariantProps<typeof listboxItemVariants>["size"]>;

export type ListboxItemVariantProps = StrictVariantProps<typeof listboxItemVariants>;

export type ListboxItemProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ListboxItemVariantProps;

export function ListboxItem({ size, render, ...props }: ListboxItemProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: listboxItemVariants({ size }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
