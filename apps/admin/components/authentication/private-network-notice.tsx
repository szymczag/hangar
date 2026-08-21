/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// components
import { CodeBlock } from "@/components/common/code-block";

type Props = {
  /** Provider prefix used by the allowlist variables, e.g. "GITLAB". */
  provider: string;
  /** Human-readable provider name. */
  label: string;
};

/**
 * Explains why a self-hosted provider on an internal network is unreachable
 * until the deployment operator allows it.
 *
 * Outbound authentication requests are pinned to an address that was validated
 * as public, which is what stops a hostname from being re-pointed at an
 * internal service between the check and the connection. A self-managed
 * instance behind a private address is a legitimate destination, so it has to
 * be named explicitly — and only by whoever controls the deployment, since
 * granting it from this panel would let an admin aim credential-bearing
 * requests into the internal network.
 */
export function PrivateNetworkNotice(props: Props) {
  const { provider, label } = props;

  return (
    <div className="flex flex-col gap-y-2 rounded-lg bg-layer-3 px-6 py-4">
      <div className="text-16 font-medium">Self-hosted {label} on a private network</div>
      <div className="text-13 leading-5 text-tertiary">
        Requests to {label} may only reach public addresses. A self-managed instance on an internal address is refused
        until the deployment names it, using <CodeBlock darkerShade>{provider}_ALLOWED_IPS</CodeBlock> (comma-separated
        CIDRs) or <CodeBlock darkerShade>{provider}_ALLOWED_HOSTS</CodeBlock> (comma-separated hostnames).
      </div>
      <div className="text-13 leading-5 text-tertiary">
        These are environment variables on purpose and cannot be set here: they permit outbound authentication traffic,
        carrying a client secret, to addresses inside your network. That belongs to whoever owns the deployment rather
        than to anyone with access to this panel. Allowlisting widens which addresses are acceptable; the connection is
        still pinned and the peer re-checked.
      </div>
    </div>
  );
}
