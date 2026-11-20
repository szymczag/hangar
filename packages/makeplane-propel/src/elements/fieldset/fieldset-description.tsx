import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type FieldsetDescriptionVariantProps, fieldsetDescriptionVariants } from "./variants";

export type { FieldsetDescriptionSize } from "./variants";

export type FieldsetDescriptionProps = Omit<useRender.ComponentProps<"p">, "className" | "style"> &
  FieldsetDescriptionVariantProps;

/** Supporting text shown below the fieldset legend. */
export function FieldsetDescription({ render, size, ...props }: FieldsetDescriptionProps) {
  const defaultProps: useRender.ElementProps<"p"> = {
    className: fieldsetDescriptionVariants({ size }),
  };
  return useRender({ defaultTagName: "p", render, props: mergeProps(defaultProps, props) });
}
