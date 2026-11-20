import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { listVariants, type ListVariantProps } from "./variants";
export type { ListGap } from "./variants";

export type ListProps = Omit<useRender.ComponentProps<"div">, "className" | "style"> &
  ListVariantProps;

/**
 * The styled vertical list frame. Base-UI-agnostic — graft the roving-tabindex `Composite` behavior
 * in `components` via `<Composite render={<List/>} />`. Compose `ListItem` rows inside. The `gap`
 * prop controls row spacing. @default gap="0.5"
 */
export function List({ render, gap, ...props }: ListProps) {
  const defaultProps: useRender.ElementProps<"div"> = { className: listVariants({ gap }) };
  return useRender({ defaultTagName: "div", render, props: mergeProps(defaultProps, props) });
}
