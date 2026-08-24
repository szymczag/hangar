/**
 * Copyright (c) 2026-present Maciej Szymczak and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Upload } from "lucide-react";
// plane internal packages
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AuthService, InstanceIdentityImportService } from "@plane/services";
import type { TIdentityImportPreview } from "@plane/services";
import type { IFormattedInstanceConfiguration } from "@plane/types";
// components
import { CodeBlock } from "@/components/common/code-block";

const authService = new AuthService();
const importService = new InstanceIdentityImportService();

// Why each refusal happened, in the operator's terms. Without this the console
// would show a bare code for conditions that are not guessable — most of all
// ACCOUNT_ALREADY_FEDERATED, which looks like a duplicate but is not.
const REFUSAL_REASONS: Record<string, string> = {
  INVALID_SUBJECT: "The row has no subject, or no subject_format for a SAML import.",
  DUPLICATE_SUBJECT: "The same subject appears twice in this file.",
  USER_IDENTIFIER_REQUIRED: "The row names neither a user_id nor an email.",
  USER_NOT_FOUND: "No account on this instance matches the row.",
  BINDING_OWNED_BY_ANOTHER_USER: "That subject already signs in as a different account.",
  ACCOUNT_ALREADY_FEDERATED:
    "The account already signs in through this issuer. A second identity would not replace the first — it would add another, independent way into the account, and the original would keep working.",
};

type Props = {
  config: IFormattedInstanceConfiguration;
};

/** Issuers we can name with certainty, so a typo is a choice and not an accident. */
function suggestedIssuer(provider: string, config: IFormattedInstanceConfiguration): string {
  if (provider === "google") return "https://accounts.google.com";
  if (provider === "oidc") return config["OIDC_ISSUER"] ?? "";
  if (provider === "saml") return config["SAML_IDP_ENTITY_ID"] ?? "";
  return "";
}

export function InstanceIdentityImportForm(props: Props) {
  const { config } = props;
  // states
  const [csrfToken, setCsrfToken] = useState<string | undefined>(undefined);
  const [providers, setProviders] = useState<string[]>([]);
  const [provider, setProvider] = useState("google");
  const [issuer, setIssuer] = useState(suggestedIssuer("google", config));
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TIdentityImportPreview | null>(null);
  const [password, setPassword] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    authService.requestCSRFToken().then((data) => data?.csrf_token && setCsrfToken(data.csrf_token));
    importService
      .providers()
      .then((data) => setProviders(data.providers))
      .catch(() => setProviders(["google", "oidc", "saml"]));
  }, []);

  const suggestion = useMemo(() => suggestedIssuer(provider, config), [provider, config]);

  // Any change to what would be imported invalidates the preview: the grant is
  // bound to one file, and showing a stale review next to new inputs is how an
  // operator confirms something they did not read.
  const resetPreview = () => {
    setPreview(null);
    setPassword("");
  };

  const onProviderChange = (next: string) => {
    setProvider(next);
    setIssuer(suggestedIssuer(next, config));
    resetPreview();
  };

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    resetPreview();
  };

  const runPreview = async () => {
    if (!csrfToken || !file) return;
    setIsBusy(true);
    try {
      setPreview(await importService.preview(csrfToken, { file, provider, issuer }));
    } catch (error) {
      const message = (error as { error?: { message?: string } })?.error?.message;
      setToast({ type: TOAST_TYPE.ERROR, title: "Preview failed", message: message ?? "The file could not be read." });
    } finally {
      setIsBusy(false);
    }
  };

  const runConfirm = async () => {
    // The same File object from the preview is sent again — never a second
    // pick from the operator. The server rejects a mismatched digest anyway,
    // but asking twice would be friction pretending to be a safeguard.
    if (!csrfToken || !file || !preview?.grant) return;
    setIsBusy(true);
    try {
      const result = await importService.confirm(csrfToken, {
        file,
        provider,
        issuer,
        grant: preview.grant,
        password,
      });
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Import applied",
        message: `${result.report.imported_count} identities linked, ${result.report.existing_count} already present.`,
      });
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      resetPreview();
    } catch (error) {
      const message = (error as { error?: { message?: string } })?.error?.message;
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Import not applied",
        message: message ?? "Nothing was changed.",
      });
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex max-w-4xl flex-col gap-8">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-primary" htmlFor="identity-import-provider">
            Identity provider
          </label>
          <select
            id="identity-import-provider"
            className="text-sm rounded-md border border-strong bg-surface-1 px-3 py-2"
            value={provider}
            onChange={(event) => onProviderChange(event.target.value)}
          >
            {providers.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-primary" htmlFor="identity-import-issuer">
            Issuer
          </label>
          <input
            id="identity-import-issuer"
            className="text-sm rounded-md border border-strong bg-surface-1 px-3 py-2"
            value={issuer}
            onChange={(event) => {
              setIssuer(event.target.value);
              resetPreview();
            }}
          />
          <p className="text-xs text-tertiary">
            {suggestion && issuer !== suggestion ? (
              <>
                This does not match the configured issuer <CodeBlock darkerShade>{suggestion}</CodeBlock>. An issuer
                that no sign-in ever asserts produces identities nothing will match — the import reports success and
                nobody can sign in.
              </>
            ) : (
              <>Must match the issuer the provider asserts, exactly.</>
            )}
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-primary" htmlFor="identity-import-file">
          Mapping CSV
        </label>
        <input
          id="identity-import-file"
          ref={fileInput}
          type="file"
          accept=".csv,text/csv"
          className="text-sm"
          onChange={onFileChange}
        />
        <p className="text-xs text-tertiary">
          Columns: <CodeBlock darkerShade>subject</CodeBlock>, <CodeBlock darkerShade>subject_format</CodeBlock>, and{" "}
          <CodeBlock darkerShade>email</CodeBlock> or <CodeBlock darkerShade>user_id</CodeBlock>. Up to 5 MiB; larger
          exports belong in the CLI.
        </p>
      </div>

      <div>
        <Button variant="primary" onClick={runPreview} disabled={!file || !issuer || isBusy} loading={isBusy}>
          <Upload className="h-4 w-4" /> Preview import
        </Button>
      </div>

      {preview && (
        <div className="flex flex-col gap-4 rounded-md border border-strong p-4">
          <div className="flex items-center gap-2">
            {preview.valid ? (
              <CheckCircle2 className="text-success h-5 w-5" />
            ) : (
              <AlertTriangle className="text-danger h-5 w-5" />
            )}
            <span className="text-sm font-medium text-primary">
              {preview.valid
                ? `${preview.report.imported_count} to link, ${preview.report.existing_count} already linked, of ${preview.report.row_count} rows`
                : `Refused: ${preview.report.errors.length} of ${preview.report.row_count} rows cannot be imported`}
            </span>
          </div>

          {!preview.valid && (
            <p className="text-xs text-tertiary">
              Nothing was written. A file is imported whole or not at all, so one unusable row stops all of them — there
              is no half-applied import to reconcile afterwards.
            </p>
          )}

          <div className="max-h-80 overflow-auto">
            <table className="text-sm w-full text-left">
              <thead className="text-xs text-tertiary uppercase">
                <tr>
                  <th className="py-1 pr-4">Line</th>
                  <th className="py-1 pr-4">{preview.valid ? "Account" : "Problem"}</th>
                  <th className="py-1 pr-4">{preview.valid ? "Subject" : "What it means"}</th>
                  {preview.valid && <th className="py-1">Action</th>}
                </tr>
              </thead>
              <tbody>
                {preview.valid
                  ? preview.rows.map((row) => (
                      <tr key={row.line} className="border-t border-subtle">
                        <td className="py-1 pr-4 text-tertiary">{row.line}</td>
                        <td className="py-1 pr-4">{row.email}</td>
                        <td className="font-mono text-xs py-1 pr-4">{row.subject}</td>
                        <td className="text-xs py-1">
                          {row.action === "link" ? "will be linked" : "already linked — no change"}
                        </td>
                      </tr>
                    ))
                  : preview.report.errors.map((error) => (
                      <tr key={`${error.line}-${error.code}`} className="border-t border-subtle">
                        <td className="py-1 pr-4 text-tertiary">{error.line}</td>
                        <td className="font-mono text-xs py-1 pr-4">{error.code}</td>
                        <td className="text-xs py-1 pr-4">
                          {REFUSAL_REASONS[error.code] ?? "This row cannot be imported."}
                          {error.first_line ? ` First seen on line ${error.first_line}.` : ""}
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>

          {preview.valid && (
            <div className="flex flex-col gap-3 border-t border-subtle pt-4">
              <p className="text-sm text-secondary">
                Applying this grants each listed account the ability to sign in through {provider}. Re-enter your
                password to confirm — your security key proved this session, this proves it is still you.
              </p>
              <input
                type="password"
                autoComplete="current-password"
                className="text-sm max-w-sm rounded-md border border-strong bg-surface-1 px-3 py-2"
                placeholder="Your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <div>
                <Button variant="primary" onClick={runConfirm} disabled={!password || isBusy} loading={isBusy}>
                  Apply import
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
