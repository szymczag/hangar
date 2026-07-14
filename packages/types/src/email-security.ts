/** Public metadata for a user's OpenPGP email key. The certificate is never returned. */
export interface IOpenPGPEmailKey {
  id: string;
  version: number;
  primary_fingerprint: string;
  encryption_subkey_fingerprint: string;
  primary_algorithm: string;
  encryption_algorithm: string;
  encryption_key_size: number | null;
  key_created_at: string | null;
  key_expires_at: string | null;
  last_validated_at: string | null;
  verified_at: string | null;
  status: "pending" | "active" | "replaced" | "revoked" | "expired" | "invalid";
  created_at: string;
}

export interface IEmailSecurityStatus {
  enabled: boolean;
  notification_mode: "encrypted" | "in_app_only";
  active_key: IOpenPGPEmailKey | null;
  pending_key: IOpenPGPEmailKey | null;
  account_mail_encrypted: false;
  active_suppressions: string[];
}

export interface IOpenPGPChallenge {
  challenge_id: string;
  expires_at: string;
}

export interface IEmailReceipt {
  receipt_code: string;
  message_id: string;
  mail_type: string;
  sender: string;
  delivery_mode: "clear" | "openpgp" | "suppressed";
  status: string;
  created_at: string;
  accepted_at: string | null;
  delivered_at: string | null;
  key_fingerprint: string | null;
  id?: string;
  recipient_user_id?: string | null;
  recipient_email_hash?: string;
  recipient_email?: string | null;
  template_key?: string;
  policy_class?: string;
  configuration_set?: string;
  provider_message_id?: string | null;
  attempts?: number;
  last_error_code?: string | null;
}

export interface IEmailReceiptList {
  results: IEmailReceipt[];
}

export interface IAdminEmailReceiptList extends IEmailReceiptList {
  status_counts: Record<string, number>;
  oldest_due_age_seconds: number;
}

export interface IEmailSuppression {
  id: string;
  recipient_user_id: string | null;
  recipient_email: string | null;
  email_hash: string;
  reason: string;
  source: string;
  created_at: string;
}
