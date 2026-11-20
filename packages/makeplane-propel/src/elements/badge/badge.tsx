import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type BadgeVariantProps, badgeVariants } from "./variants";

export type { BadgeSize, BadgeVariant } from "./variants";

export type BadgeProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> &
  BadgeVariantProps;

/**
 * The badge pill: the styled inline-flex container. Compose a `BadgeIcon` and `BadgeLabel` inside
 * it (or use the ready-made `components/badge` composition). Sets the variant's text color and the
 * size's `--node-size`, which its slot children inherit.
 */
export function Badge({ variant, size, render, ...props }: BadgeProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: badgeVariants({ variant, size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
