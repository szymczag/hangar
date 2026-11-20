import {
  SelectFooter as SelectFooterElement,
  type SelectFooterProps as SelectFooterElementProps,
} from "../../elements/select";

export type SelectFooterProps = SelectFooterElementProps;

/**
 * A non-interactive footer pinned below the list (a hint, a count) — the same chrome as
 * `MenuFooter`. Pass it through `SelectContent`'s `footer`.
 */
export function SelectFooter(props: SelectFooterProps) {
  return <SelectFooterElement {...props} />;
}
