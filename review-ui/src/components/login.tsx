import { useState } from "react";
import { useNavigate } from "react-router";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

export function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [needsNewPassword, setNeedsNewPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let challengeSession: string | undefined;
      if (needsNewPassword) {
        const raw = sessionStorage.getItem("ibrary_review_pw_challenge");
        if (!raw) throw new Error("Password challenge expired. Sign in again.");
        challengeSession = (JSON.parse(raw) as { session: string }).session;
      }

      const result = await login(email, password, {
        newPassword: needsNewPassword ? newPassword : undefined,
        challengeSession,
      });

      if (result === "NEW_PASSWORD_REQUIRED") {
        setNeedsNewPassword(true);
        setError("");
        return;
      }

      navigate("/queue");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 px-4">
      <div className="w-full max-w-md rounded-lg border bg-white p-8 shadow-sm">
        <div className="mb-8 text-center">
          <h1 className="mb-2 text-2xl font-semibold text-neutral-900">IBrary Reviewer</h1>
          <p className="text-sm text-neutral-600">
            Review curated biology lessons before publication
          </p>
        </div>
        {error && (
          <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={loading || needsNewPassword}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">
              {needsNewPassword ? "Temporary password" : "Password"}
            </Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
            />
          </div>
          {needsNewPassword && (
            <div className="space-y-2">
              <Label htmlFor="newPassword">New password</Label>
              <Input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={10}
                disabled={loading}
              />
              <p className="text-xs text-neutral-500">
                At least 10 characters with upper, lower, and a number.
              </p>
            </div>
          )}
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Signing in...
              </>
            ) : needsNewPassword ? (
              "Set password and continue"
            ) : (
              "Sign in"
            )}
          </Button>
        </form>
        <div className="mt-6 rounded border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-700">
          <p className="mb-1 font-medium">Sign in with your Cognito user</p>
          <p>Use the email and password from admin setup (admin or reviewer group).</p>
        </div>
      </div>
    </div>
  );
}
