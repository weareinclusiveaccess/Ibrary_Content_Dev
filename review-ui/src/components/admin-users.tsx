import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { ArrowLeft, Loader2, UserPlus } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import {
  createPortalUser,
  fetchCognitoStatus,
  fetchPortalUsers,
  type ApiCognitoStatus,
  type ApiPortalUser,
} from "@/lib/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

export function AdminUsers() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [status, setStatus] = useState<ApiCognitoStatus | null>(null);
  const [users, setUsers] = useState<ApiPortalUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"reviewer" | "admin">("reviewer");
  const [tempPassword, setTempPassword] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const st = await fetchCognitoStatus();
      setStatus(st);
      if (st.enabled) {
        setUsers(await fetchPortalUsers());
      } else {
        setUsers([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      navigate("/");
      return;
    }
    if (user.role !== "admin") {
      navigate("/queue");
      return;
    }
    load();
  }, [user, navigate, load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    setError("");
    try {
      await createPortalUser({
        email,
        role,
        temporary_password: tempPassword,
        send_invite: false,
      });
      setEmail("");
      setTempPassword("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  };

  if (!user || user.role !== "admin") return null;

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" asChild>
              <Link to="/queue">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Queue
              </Link>
            </Button>
            <h1 className="text-lg font-semibold">Manage users</h1>
          </div>
          <Button variant="outline" size="sm" onClick={() => { logout(); navigate("/"); }}>
            Sign out
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-8 px-6 py-8">
        {status && !status.enabled && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            <p className="font-medium">Cognito not connected to this API</p>
            <p className="mt-1 text-amber-800">
              Run <code className="text-xs">terraform apply</code> in{" "}
              <code className="text-xs">infra/terraform/environments/dev</code>, then set{" "}
              <code className="text-xs">COGNITO_USER_POOL_ID</code> on the API and attach the IAM
              policy from output <code className="text-xs">cognito_admin_api_policy_arn</code>.
            </p>
          </div>
        )}

        {status?.enabled && (
          <p className="text-sm text-neutral-600">
            Pool <code className="text-xs">{status.user_pool_id}</code> · groups:{" "}
            {status.groups.join(", ")}
          </p>
        )}

        <form onSubmit={handleCreate} className="space-y-4 rounded-lg border bg-white p-6">
          <h2 className="flex items-center gap-2 text-sm font-medium">
            <UserPlus className="h-4 w-4" />
            Create user
          </h2>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={creating || !status?.enabled}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="role">Role</Label>
            <select
              id="role"
              className="h-9 w-full rounded-md border px-3 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value as "admin" | "reviewer")}
              disabled={creating || !status?.enabled}
            >
              <option value="reviewer">Reviewer</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tempPassword">Temporary password (min 10 chars)</Label>
            <Input
              id="tempPassword"
              type="password"
              required
              minLength={10}
              value={tempPassword}
              onChange={(e) => setTempPassword(e.target.value)}
              disabled={creating || !status?.enabled}
            />
            <p className="text-xs text-neutral-500">
              User must change password on first login (Cognito policy).
            </p>
          </div>
          <Button type="submit" disabled={creating || !status?.enabled}>
            {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Create user
          </Button>
        </form>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="rounded-lg border bg-white">
          <h2 className="border-b px-4 py-3 text-sm font-medium">Users</h2>
          {loading ? (
            <p className="p-6 text-center text-neutral-500">Loading…</p>
          ) : users.length === 0 ? (
            <p className="p-6 text-sm text-neutral-500">No users yet</p>
          ) : (
            <ul className="divide-y">
              {users.map((u) => (
                <li key={u.username} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                  <div>
                    <p className="font-medium">{u.email}</p>
                    <p className="text-xs text-neutral-500">{u.status}</p>
                  </div>
                  <div className="flex gap-1">
                    {u.groups.map((g) => (
                      <Badge key={g} variant="secondary" className="text-xs">
                        {g}
                      </Badge>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  );
}
