/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { SOURCE_CODE_URL } from "@plane/constants";
// assets
import { HangarMark } from "@plane/propel/icons";
import { useInstance } from "@/hooks/store/use-instance";

type TPoweredBy = {
  disabled?: boolean;
};

export function PoweredBy(props: TPoweredBy) {
  // props
  const { disabled = false } = props;
  const { config } = useInstance();
  const sourceUrl = config?.product?.source_url ?? SOURCE_CODE_URL;

  if (disabled || !sourceUrl) return null;

  return (
    <a
      href={sourceUrl}
      className="fixed right-5 bottom-2.5 !z-[999999] flex items-center gap-1 rounded-sm border border-subtle bg-layer-3 px-2 py-1 shadow-raised-100"
      target="_blank"
      rel="noreferrer noopener"
    >
      <HangarMark className="size-3 text-primary" />
      <div className="text-11">
        Powered by <span className="font-semibold">Hangar Publish</span>
      </div>
    </a>
  );
}
