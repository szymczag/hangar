import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { avatarGroupOverflowVariants } from "./variants";

export type AvatarGroupOverflowProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
>;

/** Unclipped wrapper for the counter's tooltip trigger; behavior belongs to the ready-made. */
export function AvatarGroupOverflow({ render, ...props }: AvatarGroupOverflowProps) {
  const defaultProps: useRender.ElementProps<"span"> = { className: avatarGroupOverflowVariants() };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
