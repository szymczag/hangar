import { NavigationMenu as BaseNavigationMenu } from "@base-ui/react/navigation-menu";

import {
  NavigationMenuLink as NavigationMenuLinkElement,
  type NavigationMenuLinkProps as NavigationMenuLinkElementProps,
} from "../../elements/navigation-menu";

export type NavigationMenuLinkProps = Omit<BaseNavigationMenu.Link.Props, "className" | "style"> &
  Pick<NavigationMenuLinkElementProps, "appearance">;

/**
 * The ready-made navigable link: grafts Base UI's `NavigationMenu.Link` behavior onto the styled
 * link. `appearance="item"` is a top-level pill beside the triggers; `appearance="card"` is a
 * stacked entry inside a `NavigationMenuContent`, pairing a `NavigationMenuLinkTitle` with an
 * optional `NavigationMenuLinkDescription`.
 */
export function NavigationMenuLink({ appearance, ...props }: NavigationMenuLinkProps) {
  return (
    <BaseNavigationMenu.Link
      {...props}
      render={<NavigationMenuLinkElement appearance={appearance} />}
    />
  );
}
