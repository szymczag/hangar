/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
// ui
import { Button } from "@plane/propel/button";
import { CopyIcon } from "@plane/propel/icons";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";

type Props = {
  label: string;
  url: string;
  description: string | React.ReactNode;
};

export type TCopyField = {
  key: string;
  label: string;
  url: string;
  description: string | React.ReactNode;
};

export function CopyField(props: Props) {
  const { label, url, description } = props;

  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-13 text-secondary">{label}</h4>
      <Button
        variant="secondary"
        size="lg"
        className="flex w-full items-center justify-between gap-2 py-2"
        title={url}
        onClick={() => {
          navigator.clipboard.writeText(url);
          setToast({
            type: TOAST_TYPE.INFO,
            title: "Copied to clipboard",
            message: `The ${label} has been successfully copied to your clipboard`,
          });
        }}
      >
        {/* These are long enough to overflow the button. Scrolling keeps the
            whole value reachable, and the button copies all of it regardless of
            what is visible. */}
        <span className="min-w-0 flex-1 overflow-x-auto text-left text-13 font-medium whitespace-nowrap">{url}</span>
        <CopyIcon width={18} height={18} color="#B9B9B9" className="shrink-0" />
      </Button>
      <div className="text-11 text-tertiary">{description}</div>
    </div>
  );
}
