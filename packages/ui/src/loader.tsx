/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
// helpers
import { cn } from "./utils";

type Props = {
  children: React.ReactNode;
  className?: string;
};

// forwardRef so the loader can be the single child of a Fragment-backed Headless UI Transition,
// which throws "Did you forget to passthrough the `ref` to the actual DOM node?" otherwise.
const Loader = React.forwardRef<HTMLDivElement, Props>(function Loader({ children, className = "" }, ref) {
  return (
    <div ref={ref} className={cn("animate-pulse", className)} role="status">
      {children}
    </div>
  );
}) as React.ForwardRefExoticComponent<Props & React.RefAttributes<HTMLDivElement>> & { Item: typeof Item };

type ItemProps = {
  height?: string;
  width?: string;
  className?: string;
};

function Item({ height = "auto", width = "auto", className = "" }: ItemProps) {
  return <div className={cn("rounded-md bg-layer-1", className)} style={{ height: height, width: width }} />;
}

Loader.Item = Item;

Loader.displayName = "plane-ui-loader";

export { Loader };
