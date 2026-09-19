/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useState, useRef, useCallback, useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useDropzone } from "react-dropzone";
import { Popover } from "@headlessui/react";
// plane imports
import { ACCEPTED_COVER_IMAGE_MIME_TYPES_FOR_REACT_DROPZONE, MAX_FILE_SIZE } from "@plane/constants";
import { useOutsideClickDetector } from "@plane/hooks";
import { Tabs } from "@plane/propel/tabs";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { EFileAssetType } from "@plane/types";
// helpers
import { STATIC_COVER_IMAGES, getCoverImageDisplayURL } from "@/helpers/cover-image.helper";
// hooks
import { useDropdownKeyDown } from "@/hooks/use-dropdown-key-down";
// services
import { FileService } from "@/services/file.service";

type TTabOption = {
  key: string;
  title: string;
  isEnabled: boolean;
};

type Props = {
  label: string | React.ReactNode;
  value: string | null;
  onChange: (data: string) => void;
  disabled?: boolean;
  tabIndex?: number;
  isProfileCover?: boolean;
  projectId?: string | null;
};

// services
const fileService = new FileService();

export const ImagePickerPopover = observer(function ImagePickerPopover(props: Props) {
  const { label, value, onChange, disabled = false, tabIndex, isProfileCover = false, projectId } = props;
  // states
  const [image, setImage] = useState<File | null>(null);
  const [isImageUploading, setIsImageUploading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  // refs
  const ref = useRef<HTMLDivElement>(null);
  // router params
  const { workspaceSlug } = useParams();
  // derived values
  // Covers are this instance's own images: the bundled ones, or an upload.
  // Nothing is picked from another host, which the Content-Security-Policy's
  // img-src would refuse to show anyway (docs/content-security-policy.md).
  const tabOptions: TTabOption[] = useMemo(
    () => [
      {
        key: "images",
        title: "Images",
        isEnabled: true,
      },
      {
        key: "upload",
        title: "Upload",
        // An uploaded cover is stored against the project it belongs to, so
        // there is nowhere to put one while the project is still being filled
        // in. Offering the tab there produced an upload that always failed.
        isEnabled: isProfileCover || Boolean(projectId),
      },
    ],
    [isProfileCover, projectId]
  );

  const enabledTabs = useMemo(() => tabOptions.filter((tab) => tab.isEnabled), [tabOptions]);

  const imagePickerRef = useRef<HTMLDivElement>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setImage(acceptedFiles[0]);
  }, []);

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: ACCEPTED_COVER_IMAGE_MIME_TYPES_FOR_REACT_DROPZONE,
    maxSize: MAX_FILE_SIZE,
  });

  const handleStaticImageSelect = (imageUrl: string) => {
    onChange(imageUrl);
    setIsOpen(false);
  };

  const handleSubmit = async () => {
    if (!image) return;
    setIsImageUploading(true);

    const uploadCallback = (url: string) => {
      onChange(url);
      setIsImageUploading(false);
      setImage(null);
      setIsOpen(false);
    };

    if (isProfileCover) {
      await fileService
        .uploadUserAsset(
          {
            entity_identifier: "",
            entity_type: EFileAssetType.USER_COVER,
          },
          image
        )
        .then((res) => uploadCallback(res.asset_url))
        .catch((error) => {
          console.error("Error uploading user cover image:", error);
          setIsImageUploading(false);
          setToast({
            message: error?.error ?? "The image could not be uploaded",
            type: TOAST_TYPE.ERROR,
            title: "Image not uploaded",
          });
        });
    } else {
      if (!workspaceSlug) return;
      await fileService
        .uploadWorkspaceAsset(
          workspaceSlug.toString(),
          {
            entity_identifier: projectId?.toString() ?? "",
            entity_type: EFileAssetType.PROJECT_COVER,
          },
          image
        )
        .then((res) => uploadCallback(res.asset_url))
        .catch((error) => {
          console.error("Error uploading project cover image:", error);
          setIsImageUploading(false);
          setToast({
            message: error?.error ?? "The image could not be uploaded",
            type: TOAST_TYPE.ERROR,
            title: "Image not uploaded",
          });
        });
    }
  };

  const handleClose = () => {
    if (isOpen) setIsOpen(false);
  };

  const toggleDropdown = () => {
    setIsOpen((prevIsOpen) => !prevIsOpen);
  };

  const handleKeyDown = useDropdownKeyDown(toggleDropdown, handleClose);

  const handleOnClick = (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
    e.stopPropagation();
    e.preventDefault();
    toggleDropdown();
  };

  useOutsideClickDetector(ref, handleClose);

  return (
    <Popover className="relative z-19" ref={ref} tabIndex={tabIndex} onKeyDown={handleKeyDown}>
      <Popover.Button className={getButtonStyling("secondary", "sm")} onClick={handleOnClick} disabled={disabled}>
        {label}
      </Popover.Button>

      {isOpen && (
        <Popover.Panel
          className="absolute right-0 z-20 mt-2 rounded-md border border-subtle bg-surface-1 shadow-raised-200"
          static
        >
          <div
            ref={imagePickerRef}
            className="flex h-96 w-80 flex-col overflow-auto rounded border border-subtle bg-surface-1 shadow-raised-200 md:h-[36rem] md:w-[36rem]"
          >
            <Tabs defaultValue={enabledTabs[0]?.key || "images"} className="flex h-full flex-col p-3">
              <Tabs.List className="flex rounded bg-layer-3 p-1">
                {enabledTabs.map((tab) => (
                  <Tabs.Trigger key={tab.key} value={tab.key} size="md">
                    {tab.title}
                  </Tabs.Trigger>
                ))}
                <Tabs.Indicator />
              </Tabs.List>
              <div className="vertical-scrollbar mt-3 scrollbar-sm flex-1 overflow-x-hidden overflow-y-auto p-3">
                <Tabs.Content value="images" className="h-full w-full space-y-4">
                  <div className="grid grid-cols-4 gap-4">
                    {Object.values(STATIC_COVER_IMAGES).map((imageUrl, index) => (
                      <button
                        type="button"
                        key={imageUrl}
                        className="relative col-span-2 aspect-video md:col-span-1"
                        onClick={() => handleStaticImageSelect(imageUrl)}
                      >
                        <img
                          src={imageUrl}
                          alt={`Cover ${index + 1}`}
                          className="absolute top-0 left-0 h-full w-full cursor-pointer rounded-sm object-cover transition-opacity hover:opacity-80"
                        />
                      </button>
                    ))}
                  </div>
                </Tabs.Content>
                <Tabs.Content value="upload" className="h-full w-full">
                  <div className="flex h-full w-full flex-col gap-y-2">
                    <div className="flex w-full flex-1 items-center gap-3">
                      <div
                        {...getRootProps()}
                        className={`relative grid h-full w-full cursor-pointer place-items-center rounded-lg p-12 text-center focus:ring-2 focus:ring-accent-strong focus:ring-offset-2 focus:outline-none ${
                          (image === null && isDragActive) || !value
                            ? "border-2 border-dashed border-subtle hover:bg-surface-2"
                            : ""
                        }`}
                      >
                        <button
                          type="button"
                          className="absolute top-0 right-0 z-40 -translate-y-1/2 rounded-sm bg-surface-2 px-2 py-0.5 text-11 font-medium text-secondary"
                        >
                          Edit
                        </button>
                        {image !== null || (value && value !== "") ? (
                          <>
                            <img
                              src={image ? URL.createObjectURL(image) : getCoverImageDisplayURL(value, "")}
                              alt="Cover preview"
                              className="h-full w-full rounded-lg object-cover"
                            />
                          </>
                        ) : (
                          <div>
                            <span className="mt-2 block text-13 font-medium text-secondary">
                              {isDragActive ? "Drop image here to upload" : "Drag & drop image here"}
                            </span>
                          </div>
                        )}

                        <input {...getInputProps()} />
                      </div>
                    </div>
                    {fileRejections.length > 0 && (
                      <p className="text-13 text-danger-primary">
                        {fileRejections[0].errors[0].code === "file-too-large"
                          ? "The image size cannot exceed 5 MB."
                          : "Please upload a file in a valid format."}
                      </p>
                    )}

                    <p className="text-13 text-secondary">File formats supported- .jpeg, .jpg, .png, .webp</p>

                    <div className="flex h-12 items-start justify-end gap-2">
                      <Button
                        variant="secondary"
                        onClick={() => {
                          setIsOpen(false);
                          setImage(null);
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="primary"
                        className="w-full"
                        onClick={handleSubmit}
                        disabled={!image}
                        loading={isImageUploading}
                      >
                        {isImageUploading ? "Uploading" : "Upload & Save"}
                      </Button>
                    </div>
                  </div>
                </Tabs.Content>
              </div>
            </Tabs>
          </div>
        </Popover.Panel>
      )}
    </Popover>
  );
});
