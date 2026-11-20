import * as React from "react";

type PayloadChildrenProps<Payload> = {
  /** A payload root's function children. */
  render: (state: { payload: Payload | undefined }) => React.ReactNode;
  payload: Payload | undefined;
};

function PayloadChildrenImpl<Payload>({ render, payload }: PayloadChildrenProps<Payload>) {
  return render({ payload });
}

/**
 * Renders a Base UI payload root's function children, re-running them only when the function or the
 * payload changes. The root also re-renders on internal store ticks, such as a trigger registering
 * its element. Re-running inline children there would give every trigger a new inline ref, which
 * re-registers the trigger, and loops. Parts inside read Base UI context themselves, so skipping
 * those re-runs changes nothing else.
 */
// React.memo erases generic type parameters; cast restores PayloadChildrenImpl's signature.
export const PayloadChildren = React.memo(PayloadChildrenImpl) as typeof PayloadChildrenImpl;
