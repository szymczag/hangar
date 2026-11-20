import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";
import { cva, type VariantProps } from "class-variance-authority";

import { type StrictVariantProps } from "./variant-props";

const shortcutDefaultVariants = {
  size: "md",
} as const;

export const shortcutVariants = cva("shrink-0 text-tertiary", {
  variants: {
    size: {
      sm: "text-caption-sm-regular",
      md: "text-caption-md-regular",
    },
  },
  defaultVariants: shortcutDefaultVariants,
});

type ShortcutVariantConfig = VariantProps<typeof shortcutVariants>;
export type ShortcutSize = NonNullable<ShortcutVariantConfig["size"]>;

export type ShortcutVariantProps = StrictVariantProps<
  typeof shortcutVariants,
  keyof typeof shortcutDefaultVariants
>;

export type ShortcutProps = Omit<useRender.ComponentProps<"span">, "className" | "style"> &
  ShortcutVariantProps;

export function Shortcut({ size, render, ...props }: ShortcutProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: shortcutVariants({ size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
