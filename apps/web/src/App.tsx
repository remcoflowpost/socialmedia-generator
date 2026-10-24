import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { Button } from "./components/ui/button";
import { api, ApiError } from "./lib/api";
import { cn } from "./lib/cn";
import type { User } from "./lib/types";
import { AdminPage } from "./pages/AdminPage";
import { EditorPage } from "./pages/EditorPage";
import { LibraryPage } from "./pages/LibraryPage";
import { LoginPage } from "./pages/LoginPage";
import { PostsPage } from "./pages/PostsPage";

export function App() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.get<User>("/api/auth/me") });

  if (me.isLoading) return <div className="p-8 text-muted">Laden...</div>;
  if (me.error instanceof ApiError && [401, 403].includes(me.error.status)) return <LoginPage />;
  if (!me.data) return <div className="p-8 text-danger">API niet bereikbaar.</div>;

  const user = me.data;
  const logout = async () => {
    await api.post("/api/auth/logout");
    queryClient.clear();
    await me.refetch();
  };
  const link = ({ isActive }: { isActive: boolean }) =>
    cn("rounded-md px-3 py-1.5 text-sm", isActive ? "bg-surface-2 text-foreground" : "text-muted hover:text-foreground");

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 shrink-0 items-center gap-6 border-b border-border px-4">
        <span className="font-semibold tracking-tight">Flow Social</span>
        <nav className="flex gap-1">
          <NavLink to="/posts" className={link}>Posts</NavLink>
          <NavLink to="/bibliotheek" className={link}>Bibliotheek</NavLink>
          {user.role === "admin" && <NavLink to="/admin" className={link}>Beheer</NavLink>}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-sm text-muted">
          <span>{user.email} ({user.role})</span>
          <Button variant="ghost" size="sm" onClick={logout} aria-label="Uitloggen">
            <LogOut size={16} />
          </Button>
        </div>
      </header>
      <main className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<Navigate to="/posts" replace />} />
          <Route path="/posts" element={<PostsPage />} />
          <Route path="/posts/:postId" element={<EditorPage user={user} />} />
          <Route path="/bibliotheek" element={<LibraryPage user={user} />} />
          <Route path="/admin" element={user.role === "admin" ? <AdminPage /> : <Navigate to="/posts" />} />
        </Routes>
      </main>
    </div>
  );
}
