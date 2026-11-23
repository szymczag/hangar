/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useState, useRef, useCallback, useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import { useDropzone } from "react-dropzone";
// plane imports
import { Popover, PopoverBody, PopoverContent, PopoverTrigger } from "@makeplane/propel/components/popover";
import { Tab, Tabs, TabsList, TabsPanel } from "@makeplane/propel/components/tabs";
import { ACCEPTED_COVER_IMAGE_MIME_TYPES_FOR_REACT_DROPZONE, MAX_FILE_SIZE } from "@plane/constants";
import { Button } from "@makeplane/propel/components/button";
import { Button as ButtonElement } from "@makeplane/propel/elements/button";
import { setToast } from "@plane/blocks/toast";
import { EFileAssetType } from "@plane/types";
// helpers
import { STATIC_COVER_IMAGES, getCoverImageDisplayURL } from "@/helpers/cover-image.helper";
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
  // router params
  const { workspaceSlug } = useParams();
  // derived values
  // Fork: covers are this instance's own images: the bundled ones, or an upload.
  // Nothing is picked from another host (no Unsplash, S21), which the Content-Security-Policy's
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
            type: "error",
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
            type: "error",
            title: "Image not uploaded",
          });
        });
    }
  };

  return (
    // The popover owns the portal, positioning, outside press and Escape, so the outside-click
    // detector and the dropdown key handler go (Ruling 36).
    <div className="relative z-19">
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger
          disabled={disabled}
          render={
            <ButtonElement
              variant="secondary"
              size="xs"
              stretch="auto"
              disabled={disabled}
              tabIndex={tabIndex}
              // The trigger sits inside clickable cover-image chrome; the press must not reach it.
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
              }}
            />
          }
        >
          {label}
        </PopoverTrigger>
        <PopoverContent variant="rich" side="bottom" align="end" sideOffset={8} data-prevent-outside-click>
          <PopoverBody tabIndex={0}>
            <div
              ref={imagePickerRef}
              className="flex h-96 w-80 max-w-full flex-col overflow-auto md:h-[36rem] md:w-[36rem]"
            >
              <Tabs variant="contained" stretch="full" layout="fill" defaultValue={enabledTabs[0]?.key || "images"}>
                <TabsList>
                  {enabledTabs.map((tab) => (
                    <Tab key={tab.key} value={tab.key} label={tab.title} />
                  ))}
                </TabsList>
                <div className="vertical-scrollbar mt-4 scrollbar-sm flex min-h-0 w-full flex-1 flex-col overflow-auto">
                  <TabsPanel value="images">
                    <div className="grid grid-cols-4 gap-4">
                      {Object.values(STATIC_COVER_IMAGES).map((imageUrl, index) => (
                        <button
                          type="button"
                          key={imageUrl}
                          className="relative col-span-2 aspect-video md:col-span-1"
                          aria-label={`Select cover image ${index + 1}`}
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
                  </TabsPanel>
                  <TabsPanel value="upload">
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
                          <div className="absolute top-0 right-1 z-40">
                            <Button type="button" variant="tertiary" size="xs" stretch="auto" label="Edit" />
                          </div>
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
                              <span className="mt-2 block text-body-xs-medium text-secondary">
                                {isDragActive ? "Drop image here to upload" : "Drag & drop image here"}
                              </span>
                            </div>
                          )}

                          <input {...getInputProps()} />
                        </div>
                      </div>
                      {fileRejections.length > 0 && (
                        <p className="text-body-xs-regular text-danger-primary">
                          {fileRejections[0].errors[0].code === "file-too-large"
                            ? "The image size cannot exceed 5 MB."
                            : "Please upload a file in a valid format."}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-1">
                        <p className="min-w-0 truncate text-body-xs-regular text-secondary">
                          File formats supported- .jpeg, .jpg, .png, .webp
                        </p>
                        <div className="flex flex-shrink-0 items-center gap-2">
                          <Button
                            variant="secondary"
                            size="md"
                            stretch="auto"
                            label="Cancel"
                            onClick={() => {
                              setIsOpen(false);
                              setImage(null);
                            }}
                          />
                          <Button
                            variant="primary"
                            size="md"
                            stretch="auto"
                            label={isImageUploading ? "Uploading" : "Upload & Save"}
                            onClick={handleSubmit}
                            disabled={!image}
                            loading={isImageUploading}
                          />
                        </div>
                      </div>
                    </div>
                  </TabsPanel>
                </div>
              </Tabs>
            </div>
          </PopoverBody>
        </PopoverContent>
      </Popover>
    </div>
  );
});
