import type * as React from "react";

export type ExternalAnchorProps = {
  external: boolean;
  target: React.ComponentPropsWithoutRef<"a">["target"];
  rel: React.ComponentPropsWithoutRef<"a">["rel"];
};

/**
 * Resolves the native anchor attributes controlled by an `external` convenience flag. Explicit
 * `target` and `rel` values always win, so callers retain the full native-anchor escape hatch.
 */
export function resolveExternalAnchorProps({
  external,
  target,
  rel,
}: ExternalAnchorProps): Pick<ExternalAnchorProps, "target" | "rel"> {
  return {
    target: target ?? (external ? "_blank" : undefined),
    rel: rel ?? (external ? "noreferrer noopener" : undefined),
  };
}
