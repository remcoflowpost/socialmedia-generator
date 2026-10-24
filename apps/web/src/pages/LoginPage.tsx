import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Select } from "../components/ui/input";
import { api } from "../lib/api";

export function LoginPage() {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["auth-config"], queryFn: () => api.get<{ mode: string; devUsers: string[] }>("/api/auth/config") });
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const devLogin = async () => {
    try {
      await api.post("/api/auth/dev-login", { email: email || config.data?.devUsers[0] });
      await queryClient.invalidateQueries();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="flex h-full items-center justify-center p-4">
      <Card className="w-full max-w-sm space-y-4 p-6">
        <h1 className="text-xl font-semibold">Flow Social</h1>
        <p className="text-sm text-muted">Log in met je Google Workspace-account.</p>
        {config.data?.mode === "dev" ? (
          <div className="space-y-3">
            <p className="text-xs text-warning">Ontwikkelmodus: inloggen zonder Google.</p>
            <Select value={email} onChange={(e) => setEmail(e.target.value)}>
              {config.data.devUsers.map((user) => (
                <option key={user} value={user}>{user}</option>
              ))}
            </Select>
            <Button className="w-full" onClick={devLogin}>Inloggen</Button>
          </div>
        ) : (
          <Button className="w-full" onClick={() => (window.location.href = "/api/auth/login")}>Inloggen met Google</Button>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
      </Card>
    </div>
  );
}
