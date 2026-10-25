import type { BrandKitData, Format, LayoutReport, PostDocument, TemplateDefinition } from "@flow/schema";

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "editor";
}

export interface Company {
  id: string;
  name: string;
  slug: string;
}

export interface Asset {
  id: string;
  companyId: string;
  kind: "image" | "logo" | "font" | "reference";
  filename: string;
  mime: string;
  width: number | null;
  height: number | null;
  colorProfile: string | null;
  tags: string[];
  origin: "upload" | "generated";
  provenance: Record<string, unknown>;
  parentAssetId: string | null;
  url: string;
  createdAt: string;
}

export interface Post {
  id: string;
  companyId: string;
  templateKey: string;
  title: string;
  slug: string;
  document: PostDocument;
  status: string;
  embargoUntil: string | null;
  clientApproved: boolean;
  currentVersion: number;
  updatedAt: string;
}

export interface RenderContext {
  post: Post;
  template: TemplateDefinition;
  brand: BrandKitData;
  assets: Record<string, Asset>;
  formats: Format[];
}

export interface Job {
  id: string;
  type: string;
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  error: string | null;
  result: {
    zipName: string;
    embargo: boolean;
    maxSeverity: string | null;
    version: number;
    files: { formatKey: string; name: string; severity: string | null }[];
  } | null;
}

export interface QualitySummary {
  version: number;
  reports: LayoutReport[];
  canApprove: boolean;
  reasons: string[];
}

export const formatKey = (format: Format) => `${format.platform}/${format.id}`;

// ------------------------------------------------------------------ publiceren

export type AccountStatus = "active" | "reauth_required" | "disconnected";

export interface SocialAccount {
  id: string;
  companyId: string;
  provider: "instagram" | "facebook_page" | "sandbox";
  providerLabel: string;
  name: string;
  handle: string;
  status: AccountStatus;
  statusReason: string | null;
  lastCheckedAt: string | null;
}

export interface PublishingSettings {
  timezone: string;
  slots: { id: string; weekday: number; time: string }[];
  accounts: SocialAccount[];
  sandboxEnabled: boolean;
  metaConfigured: boolean;
}

export type PublicationStatus = "scheduled" | "publishing" | "published" | "failed" | "cancelled";

export interface Publication {
  id: string;
  version: number;
  postId: string;
  postTitle: string;
  postVersionId: string;
  formatKey: string;
  account: SocialAccount;
  caption: string;
  status: PublicationStatus;
  scheduledAt: string | null;
  publishedAt: string | null;
  nextAttemptAt: string | null;
  attemptCount: number;
  providerUrl: string | null;
  failureCode: string | null;
  failureMessage: string | null;
  failureRetryable: boolean | null;
  needsConfirm: boolean;
}

export interface PublishOptions {
  timezone: string;
  version: { id: string; number: number } | null;
  exportedFormats: Record<string, { severity: string | null }>;
  approval: { approved: boolean; version: number | null; by: string | null; at: string | null };
  embargoUntil: string | null;
  accounts: (SocialAccount & {
    formats: string[];
    unsupportedFormats: string[];
    captionLimit: number | null;
    nextSlot: string | null;
  })[];
}

export interface PublishConflict {
  otherId: string;
  otherVersion: number;
  otherCaption: string;
  target: string;
}

export interface PublishErrorDetail {
  message: string;
  issues?: string[];
  conflict?: PublishConflict;
}

export interface AttemptRow {
  id: string;
  publicationId: string;
  postTitle: string;
  account: SocialAccount;
  formatKey: string;
  attemptNo: number;
  trigger: string;
  startedAt: string;
  finishedAt: string | null;
  outcome: "in_progress" | "succeeded" | "failed" | "uncertain";
  errorCode: string | null;
  httpStatus: number | null;
  providerMessage: string | null;
  providerUrl: string | null;
}
