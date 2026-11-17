/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import * as dotenv from "dotenv";
import { z } from "zod";

dotenv.config();

// Environment variable validation
const envSchema = z.object({
  APP_VERSION: z.string().default("1.0.0"),
  HOSTNAME: z.string().optional(),
  PORT: z.string().default("3000"),
  API_BASE_URL: z.string().url("API_BASE_URL must be a valid URL"),
  // CORS configuration
  CORS_ALLOWED_ORIGINS: z.string().default(""),
  // Live running location
  LIVE_BASE_PATH: z.string().default("/live"),
  // Compression options
  COMPRESSION_LEVEL: z.string().default("6").transform(Number),
  COMPRESSION_THRESHOLD: z.string().default("5000").transform(Number),
  // secret
  LIVE_SERVER_SECRET_KEY: z.string(),
  // "1" lets a throwaway development stack start with an empty or template
  // LIVE_SERVER_SECRET_KEY. Never set it on a deployment anybody else can reach.
  HANGAR_ALLOW_INSECURE_DEFAULTS: z.string().default("0"),
  // Exact hostnames that the PDF asset fetcher may intentionally reach even
  // when they resolve to private infrastructure (for example an internal S3
  // service). Connections are still pinned to the resolved address.
  PDF_ASSET_ALLOWED_HOSTS: z.string().default(""),
  // Redis configuration
  REDIS_HOST: z.string().optional(),
  REDIS_PORT: z.string().default("6379").transform(Number),
  REDIS_URL: z.string().optional(),
});

// Values the templates and older releases shipped; the installers replace the
// same list (generateSecrets in deployments/cli/community/install.sh).
export const INSECURE_LIVE_SERVER_SECRET_KEYS = [
  "htbqvBJAgpm9bzvf3r4urJer0ENReatceh",
  "change-this-key-on-deployment",
  "secret-key",
];

// Anybody who knows the secret can call the endpoints reserved for the API, so
// a published value is as good as none.
export const isInsecureLiveSecretKey = (secret: string, allowInsecureDefaults: string | undefined) =>
  allowInsecureDefaults !== "1" && (secret.trim() === "" || INSECURE_LIVE_SERVER_SECRET_KEYS.includes(secret.trim()));

const validateEnv = () => {
  const result = envSchema.safeParse(process.env);
  if (!result.success) {
    console.error("❌ Invalid environment variables:", JSON.stringify(result.error.format(), null, 4));
    process.exit(1);
  }
  if (isInsecureLiveSecretKey(result.data.LIVE_SERVER_SECRET_KEY, result.data.HANGAR_ALLOW_INSECURE_DEFAULTS)) {
    console.error(
      "❌ LIVE_SERVER_SECRET_KEY is empty or a published template value. Set the same long random value for the API and Live (for example: openssl rand -hex 32); the Compose installer generates one."
    );
    process.exit(1);
  }
  return result.data;
};

export const env = validateEnv();
