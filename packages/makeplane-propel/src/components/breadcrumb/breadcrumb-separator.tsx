import {
  BreadcrumbSeparator as BreadcrumbSeparatorSlot,
  type BreadcrumbSeparatorProps as BreadcrumbSeparatorSlotProps,
} from "../../elements/breadcrumb";
import { ChevronRightOutline } from "../../icons";

export type BreadcrumbSeparatorProps = BreadcrumbSeparatorSlotProps;

/**
 * The divider between crumbs. Defaults to a chevron — the ready-made breadcrumb owns the default
 * glyph so the `elements` slot stays a pure single element. Pass `children` to use a different
 * divider.
 */
export function BreadcrumbSeparator({ children, ...props }: BreadcrumbSeparatorProps) {
  return (
    <BreadcrumbSeparatorSlot {...props}>
      {children ?? <ChevronRightOutline aria-hidden />}
    </BreadcrumbSeparatorSlot>
  );
}
