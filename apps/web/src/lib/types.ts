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
