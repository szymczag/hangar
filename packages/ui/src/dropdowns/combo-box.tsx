/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Combobox } from "@headlessui/react";
import type { ComponentPropsWithRef, ElementType, KeyboardEventHandler, ReactElement, ReactNode, Ref } from "react";
import React, { forwardRef, useEffect, useRef, useState } from "react";

type Props = {
  as?: ElementType | undefined;
  ref?: Ref<HTMLElement> | undefined;
  tabIndex?: number | undefined;
  className?: string | undefined;
  value?: string | string[] | null;
  onChange?: (value: any) => void;
  disabled?: boolean | undefined;
  onKeyDown?: KeyboardEventHandler<HTMLDivElement> | undefined;
  multiple?: boolean;
  renderByDefault?: boolean;
  button: ReactElement<ComponentPropsWithRef<"button">, "button">;
  children: ReactNode;
};

const ComboDropDown = forwardRef(function ComboDropDown(props: Props, ref) {
  const { button, renderByDefault = true, children, ...rest } = props;

  if ((button as ReactElement).type !== "button") {
    throw new Error(
      "ComboDropDown requires one native button element so Headless UI can attach its accessibility props."
    );
  }

  const dropDownButtonRef = useRef<HTMLDivElement | null>(null);

  const [shouldRender, setShouldRender] = useState(renderByDefault);

  const onHover = () => {
    setShouldRender(true);
  };

  useEffect(() => {
    const element = dropDownButtonRef.current as any;

    if (!element) return;

    element.addEventListener("mouseenter", onHover);

    return () => {
      element?.removeEventListener("mouseenter", onHover);
    };
  }, [dropDownButtonRef, shouldRender]);

  if (!shouldRender) {
    return (
      <div ref={dropDownButtonRef} className="flex h-full items-center">
        {button}
      </div>
    );
  }

  return (
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-expect-error
    <Combobox {...rest} ref={ref}>
      <Combobox.Button {...button.props} />
      {children}
    </Combobox>
  );
});

const ComboOptions = Combobox.Options;
const ComboOption = Combobox.Option;
const ComboInput = Combobox.Input;

ComboDropDown.displayName = "ComboDropDown";

export { ComboDropDown, ComboOptions, ComboOption, ComboInput };
