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
  kind: "image" | "logo" | "font" | "reference" | "video";
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
  createdAt?: string;
  result: {
    zipName: string;
    embargo: boolean;
    maxSeverity: string | null;
    version: number;
    files: { formatKey: string; name: string; severity: string | null }[];
  } | null;
}

export interface Channel {
  id: string;
  name: string;
  platform: string;
  picture: string | null;
  disabled: boolean;
  group: string | null;
}

export interface ChannelList {
  provider: "mock" | "postiz";
  matchedCompany: boolean;
  channels: Channel[];
}

export type PublishMode = "now" | "schedule" | "draft";

export interface PublishJob extends Omit<Job, "result"> {
  result: { provider: string; group: string | null; posts: Record<string, unknown>[] } | null;
  caption: string;
  mode: PublishMode;
  date: string;
  provider: string;
  channels: string[];
  files: string[];
}

export interface QualitySummary {
  version: number;
  reports: LayoutReport[];
  canApprove: boolean;
  reasons: string[];
}

export const formatKey = (format: Format) => `${format.platform}/${format.id}`;
