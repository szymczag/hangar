import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type AvatarGroupCounterVariantProps, avatarGroupCounterVariants } from "./variants";

/** Props for {@link AvatarGroupCounter}, plus a `size`. */
export type AvatarGroupCounterProps = Omit<
  useRender.ComponentProps<"span">,
  "className" | "style"
> &
  AvatarGroupCounterVariantProps;

/**
 * The styled "+N" overflow counter that closes an avatar stack — the last rung of the Figma "Avatar
 * groups" component. It is a sibling of the avatars, not an `Avatar` itself: its surface is fixed
 * to the orange label fill as defined in `variants.ts`.
 *
 * This is the styled part only. The ready-made `AvatarGroup` from
 * `@makeplane/propel/components/avatar-group` derives the count from `max`/`total` and renders this
 * for you; reach for this element when you are composing a stack by hand.
 */
export function AvatarGroupCounter({ size, render, ...props }: AvatarGroupCounterProps) {
  const defaultProps: useRender.ElementProps<"span"> = {
    className: avatarGroupCounterVariants({ size }),
  };
  return useRender({ defaultTagName: "span", render, props: mergeProps(defaultProps, props) });
}
