import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { menuSearchInputVariants } from "./variants";

export type MenuSearchInputProps = Omit<useRender.ComponentProps<"input">, "className" | "style">;

/**
 * The styled borderless text field inside `MenuSearch`. Base-UI-agnostic — the ready-made
 * `MenuSearch` (`components`) keeps text-editing keys from bubbling so typing does not trigger the
 * menu's own type-ahead navigation, while letting Escape and the arrow keys through to the menu.
 */
export function MenuSearchInput({ render, ...props }: MenuSearchInputProps) {
  const defaultProps: useRender.ElementProps<"input"> = { className: menuSearchInputVariants() };
  return useRender({ defaultTagName: "input", render, props: mergeProps(defaultProps, props) });
}
