import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type ComboboxChipOverflowVariantProps, comboboxChipOverflowVariants } from "./variants";

export type { ComboboxChipOverflowSize } from "./variants";

export type ComboboxChipOverflowProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
> &
  ComboboxChipOverflowVariantProps;

/**
 * The "+N more" count shown after the visible chips when selection exceeds `maxVisible`. A muted,
 * non-interactive caption — the hidden values stay managed from the popup. Base-UI-agnostic.
 */
export function ComboboxChipOverflow({ render, size, ...props }: ComboboxChipOverflowProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: comboboxChipOverflowVariants({ size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
