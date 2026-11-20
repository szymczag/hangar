import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { collapsibleHeaderVariants, type CollapsibleHeaderVariantProps } from "./variants";

export type CollapsibleHeaderProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  CollapsibleHeaderVariantProps;

/**
 * The header row around the disclosure trigger. Holds the trigger (which packs the label cluster)
 * and an optional `CollapsibleTriggerTrailing` sibling at the inline-end. Layout-only — Base UI
 * Collapsible has no Header part, so this is not a behavior graft.
 */
export function CollapsibleHeader({ placement, render, ...props }: CollapsibleHeaderProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: collapsibleHeaderVariants({ placement }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}

export type { CollapsibleHeaderPlacement } from "./variants";
