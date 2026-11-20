import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import {
  collapsiblePanelContentVariants,
  type CollapsiblePanelContentVariantProps,
} from "./variants";

export type CollapsiblePanelContentProps = Omit<
  useRender.ComponentProps<"div">,
  "className" | "style"
> &
  CollapsiblePanelContentVariantProps;

/**
 * The padded inner content of a `CollapsiblePanel`: Figma inset (`px-3 pb-3`) and body prose
 * (`text-body-xs-regular text-secondary`). Lives here rather than on the panel so height animation
 * measures cleanly and List consumers that mount rows directly in the panel do not inherit
 * Collapsible typography.
 */
export function CollapsiblePanelContent({
  placement,
  hug,
  render,
  ...props
}: CollapsiblePanelContentProps) {
  const defaultProps: useRender.ElementProps<"div"> = {
    className: collapsiblePanelContentVariants({ placement, hug }),
  };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}

export type { CollapsiblePanelContentPlacement } from "./variants";
