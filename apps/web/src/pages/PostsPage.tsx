import { useMutation, useQuery } from "@tanstack/react-query";
import type { TemplateDefinition } from "@flow/schema";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Badge, Card } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input, Label, Select } from "../components/ui/input";
import { api } from "../lib/api";
import type { Company, Post } from "../lib/types";

export function PostsPage() {
  const navigate = useNavigate();
  const [companyId, setCompanyId] = useState("");
  const [open, setOpen] = useState(false);
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api.get<Company[]>("/api/companies") });
  const templates = useQuery({ queryKey: ["templates"], queryFn: () => api.get<TemplateDefinition[]>("/api/templates") });
  const posts = useQuery({
    queryKey: ["posts", companyId],
    queryFn: () => api.get<Post[]>(`/api/posts${companyId ? `?company_id=${companyId}` : ""}`),
  });

  const [draft, setDraft] = useState({ companyId: "", templateKey: "", title: "" });
  const create = useMutation({
    mutationFn: () =>
      api.post<Post>("/api/posts", {
        company_id: draft.companyId || companies.data?.[0]?.id,
        template_key: draft.templateKey || templates.data?.[0]?.key,
        title: draft.title,
      }),
    onSuccess: (post) => navigate(`/posts/${post.id}`),
  });

  const companyName = (id: string) => companies.data?.find((c) => c.id === id)?.name ?? "";
  const templateName = (key: string) => templates.data?.find((t) => t.key === key)?.name ?? key;

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Posts</h1>
        <Select className="ml-auto w-64" value={companyId} onChange={(e) => setCompanyId(e.target.value)}>
          <option value="">Alle bedrijven</option>
          {companies.data?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </Select>
        <Button onClick={() => setOpen(true)}>
          <Plus size={16} /> Nieuwe post
        </Button>
      </div>

      <div className="grid gap-2">
        {posts.data?.map((post) => (
          <Link key={post.id} to={`/posts/${post.id}`}>
            <Card className="flex items-center gap-4 hover:border-primary/60">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{post.title}</div>
                <div className="text-sm text-muted">
                  {companyName(post.companyId)} · {templateName(post.templateKey)}
                </div>
              </div>
              {post.embargoUntil && new Date(post.embargoUntil) > new Date() && <Badge tone="warning">Embargo</Badge>}
              <Badge>{post.status}</Badge>
              <span className="text-xs text-muted">v{String(post.currentVersion).padStart(3, "0")}</span>
            </Card>
          </Link>
        ))}
        {posts.data?.length === 0 && <p className="text-muted">Nog geen posts.</p>}
      </div>

      <Dialog open={open} onOpenChange={setOpen} title="Nieuwe post">
        <div className="space-y-4">
          <div>
            <Label>Afzender (bedrijf)</Label>
            <Select value={draft.companyId} onChange={(e) => setDraft({ ...draft, companyId: e.target.value })}>
              {companies.data?.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Template</Label>
            <Select value={draft.templateKey} onChange={(e) => setDraft({ ...draft, templateKey: e.target.value })}>
              {templates.data?.map((t) => (
                <option key={t.key} value={t.key}>{t.name}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Werktitel</Label>
            <Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} placeholder="Bijv. Aankondiging serie X" />
          </div>
          {create.error && <p className="text-sm text-danger">{create.error.message}</p>}
          <Button className="w-full" onClick={() => create.mutate()} disabled={create.isPending}>
            Aanmaken
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
