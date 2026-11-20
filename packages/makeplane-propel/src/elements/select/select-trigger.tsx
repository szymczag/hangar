import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type SelectTriggerVariantProps, selectTriggerVariants } from "./variants";

export type {
  SelectTriggerAnySize,
  SelectTriggerFieldSize,
  SelectTriggerPillSize,
  SelectTriggerSize,
  SelectTriggerVariant,
  SelectTriggerVariantProps,
  SelectTriggerWidth,
} from "./variants";

export type SelectTriggerProps = Omit<useRender.ComponentProps<"button">, "className" | "style"> &
  SelectTriggerVariantProps;

/**
 * The styled select trigger button — wraps its selected value and optional glyphs in one row.
 * Base-UI-agnostic — graft the select behavior in `components` via `<BaseSelect.Trigger
 * render={<SelectTrigger/>} />`.
 */
export function SelectTrigger({ size, variant, width, render, ...props }: SelectTriggerProps) {
  const defaultProps: useRender.ElementProps<"button"> = {
    className: selectTriggerVariants({ size, variant, width }),
  };
  return useRender({ defaultTagName: "button", render, props: mergeProps(defaultProps, props) });
}
