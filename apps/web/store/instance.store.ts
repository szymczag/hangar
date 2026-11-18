/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observable, action, makeObservable, runInAction } from "mobx";
// types
import type { IInstance, IInstanceConfig } from "@plane/types";
// services
import { InstanceService } from "@/services/instance.service";

type TError = {
  status: string;
  message: string;
  data?: {
    is_activated: boolean;
    is_setup_done: boolean;
  };
};

export interface IInstanceStore {
  // issues
  isLoading: boolean;
  instance: IInstance | undefined;
  config: IInstanceConfig | undefined;
  error: TError | undefined;
  // action
  fetchInstanceInfo: () => Promise<void>;
  fetchMemberInstanceInfo: () => Promise<void>;
}

export class InstanceStore implements IInstanceStore {
  isLoading: boolean = true;
  instance: IInstance | undefined = undefined;
  config: IInstanceConfig | undefined = undefined;
  error: TError | undefined = undefined;
  // services
  instanceService;

  constructor() {
    makeObservable(this, {
      // observable
      isLoading: observable.ref,
      instance: observable,
      config: observable,
      error: observable,
      // actions
      fetchInstanceInfo: action,
      fetchMemberInstanceInfo: action,
    });
    // services
    this.instanceService = new InstanceService();
  }

  /**
   * @description fetching instance information
   */
  fetchInstanceInfo = async () => {
    try {
      this.isLoading = true;
      this.error = undefined;
      const instanceInfo = await this.instanceService.getInstanceInfo();
      runInAction(() => {
        this.isLoading = false;
        this.instance = instanceInfo.instance;
        this.config = instanceInfo.config;
      });
    } catch (error) {
      runInAction(() => {
        this.isLoading = false;
        this.error = {
          status: "error",
          message: "Failed to fetch instance info",
        };
      });
      throw error;
    }
  };

  /**
   * @description adds what only a signed-in user is told — the version, the default
   * workspace, integration identifiers, limits — to the public instance information
   */
  fetchMemberInstanceInfo = async () => {
    const memberInfo = await this.instanceService.getMemberInstanceInfo();
    runInAction(() => {
      this.instance = { ...this.instance, ...memberInfo.instance } as IInstance;
      this.config = { ...this.config, ...memberInfo.config } as IInstanceConfig;
    });
  };
}
