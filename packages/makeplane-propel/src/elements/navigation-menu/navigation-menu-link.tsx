import { mergeProps } from "@base-ui/react/merge-props";
import { useRender } from "@base-ui/react/use-render";

import { type NavigationMenuLinkVariantProps, navigationMenuLinkVariants } from "./variants";

export type NavigationMenuLinkProps = Omit<useRender.ComponentProps<"a">, "className" | "style"> &
  NavigationMenuLinkVariantProps;

/**
 * A styled navigable link. `appearance="item"` is a top-level pill that shares its chrome with
 * `NavigationMenuTrigger`; `appearance="card"` is a stacked entry inside `Content`, pairing a
 * `NavigationMenuLinkTitle` with an optional `NavigationMenuLinkDescription`. Base-UI-agnostic —
 * graft in `components` via `<BaseNavigationMenu.Link render={<NavigationMenuLink appearance="…"
 * />} />`.
 */
export function NavigationMenuLink({ appearance, render, ...props }: NavigationMenuLinkProps) {
  const defaultProps: useRender.ElementProps<"a"> = {
    className: navigationMenuLinkVariants({ appearance }),
  };
  return useRender({ defaultTagName: "a", render, props: mergeProps(defaultProps, props) });
}
