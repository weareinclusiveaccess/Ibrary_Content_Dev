import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Link } from "react-router";
import { ChevronLeft, ChevronRight, FileQuestion, Search, Shield, Users } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { fetchUnits } from "@/lib/api";
import { mapUnitRow } from "@/lib/mappers";
import type { PassFail, Status, UnitRow } from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Progress } from "./ui/progress";

type QueueTab = "available" | "reviewed";

function matchesTab(unit: UnitRow, tab: QueueTab, role: "reviewer" | "admin"): boolean {
  if (role === "reviewer") {
    if (tab === "available") {
      return unit.status === "draft" || unit.status === "draft_curriculum_only";
    }
    // "My reviews" includes anything a reviewer has acted on, including rejections.
    return (
      unit.status === "verified" ||
      unit.status === "published" ||
      unit.status === "rejected"
    );
  }
  if (tab === "available") {
    // Admins see verified units waiting for approval *and* rejected units so
    // they can read the rejection reason and decide whether to send back to draft.
    return unit.status === "verified" || unit.status === "rejected";
  }
  return unit.status === "published";
}

export function ReviewQueue() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [judgeFilter, setJudgeFilter] = useState("all");
  const [activeTab, setActiveTab] = useState<QueueTab>("available");

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (searchQuery.trim()) params.set("q", searchQuery.trim());
      if (statusFilter !== "all") params.set("status", statusFilter);
      const data = await fetchUnits(params);
      const rows = data.items.map(mapUnitRow).filter((u) => matchesTab(u, activeTab, user.role));
      let filtered = rows;
      if (judgeFilter === "Passed") filtered = rows.filter((u) => u.passFail === "Passed");
      if (judgeFilter === "Failed") filtered = rows.filter((u) => u.passFail === "Failed");
      setUnits(filtered);
      setTotal(filtered.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load units");
    } finally {
      setLoading(false);
    }
  }, [user, searchQuery, statusFilter, judgeFilter, activeTab]);

  useEffect(() => {
    load();
  }, [load]);

  if (!user) {
    navigate("/");
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-10 border-b bg-white">
        <div className="mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold">IBrary Reviewer</h1>
            <Badge variant="secondary" className="text-xs">
              Dev
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span>{user.email}</span>
            {user.role === "admin" && (
              <Badge className="bg-purple-100 text-purple-700">
                <Shield className="mr-1 inline h-3 w-3" />
                Admin
              </Badge>
            )}
            {user.role === "admin" && (
              <Button variant="outline" size="sm" asChild>
                <Link to="/admin/users">
                  <Users className="mr-1 inline h-3 w-3" />
                  Manage users
                </Link>
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => { logout(); navigate("/"); }}>
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-6 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-semibold">Review queue</h2>
          <p className="text-sm text-neutral-600">
            {user.role === "admin"
              ? "Approve verified units for publication"
              : "Browse curated lessons and UDL judge scores"}
          </p>
          <div className="mt-4 flex gap-2">
            <Button
              variant={activeTab === "available" ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveTab("available")}
            >
              {user.role === "admin" ? "Pending approval" : "Available to review"}
            </Button>
            <Button
              variant={activeTab === "reviewed" ? "default" : "outline"}
              size="sm"
              onClick={() => setActiveTab("reviewed")}
            >
              {user.role === "admin" ? "Published" : "My reviews"}
            </Button>
          </div>
        </div>

        <div className="mb-4 rounded-lg border bg-white p-4">
          <div className="flex flex-wrap gap-3">
            <div className="relative min-w-[240px] flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-400" />
              <Input
                className="pl-9"
                placeholder="Search by title or unit ID"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && load()}
              />
            </div>
            <select
              className="h-9 rounded-md border px-3 text-sm"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft</option>
              <option value="draft_curriculum_only">Draft (curriculum only)</option>
              <option value="verified">Verified</option>
              <option value="rejected">Rejected</option>
              <option value="published">Published</option>
            </select>
            {user.role === "admin" && (
              <select
                className="h-9 rounded-md border px-3 text-sm"
                value={judgeFilter}
                onChange={(e) => setJudgeFilter(e.target.value)}
              >
                <option value="all">All LLM results</option>
                <option value="Passed">Passed</option>
                <option value="Failed">Failed</option>
              </select>
            )}
            <Button variant="outline" onClick={load}>
              Refresh
            </Button>
          </div>
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <div className="rounded-lg border bg-white">
          {loading ? (
            <p className="p-8 text-center text-neutral-500">Loading…</p>
          ) : units.length === 0 ? (
            <div className="flex flex-col items-center py-16">
              <FileQuestion className="mb-3 h-12 w-12 text-neutral-300" />
              <p className="text-neutral-600">No units match your filters</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b bg-neutral-50 text-left">
                    <tr>
                      <th className="p-3 font-medium">Unit ID</th>
                      <th className="p-3 font-medium">Title</th>
                      <th className="p-3 font-medium">Theme / Topic</th>
                      <th className="p-3 font-medium">Status</th>
                      {user.role === "admin" && (
                        <>
                          <th className="p-3 font-medium">LLM judge</th>
                          <th className="p-3 font-medium">Pass/Fail</th>
                        </>
                      )}
                      <th className="p-3 font-medium">Updated</th>
                      <th className="p-3 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {units.map((unit) => (
                      <tr key={unit.id} className="border-b hover:bg-neutral-50">
                        <td className="max-w-[200px] truncate p-3 font-mono text-xs">{unit.id}</td>
                        <td className="p-3">{unit.title}</td>
                        <td className="p-3 text-neutral-600">
                          {unit.theme} · {unit.topic}
                        </td>
                        <td className="p-3">
                          <StatusBadge status={unit.status} />
                        </td>
                        {user.role === "admin" && (
                          <>
                            <td className="p-3">
                              <div className="font-medium">{unit.judgeScore.toFixed(1)} / 10</div>
                              <Progress value={unit.judgeScore * 10} className="mt-1 h-1.5" />
                            </td>
                            <td className="p-3">
                              <PassFailPill passFail={unit.passFail} />
                            </td>
                          </>
                        )}
                        <td className="p-3 text-neutral-600">{unit.updated}</td>
                        <td className="p-3">
                          <Button size="sm" onClick={() => navigate(`/unit/${unit.id}`)}>
                            {user.role === "admin" ? "View" : "Review"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-neutral-600">
                <span>
                  Showing {units.length} of {total}
                </span>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled>
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button variant="outline" size="sm" disabled>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const styles: Record<Status, string> = {
    draft: "bg-neutral-100 text-neutral-700",
    draft_curriculum_only: "bg-blue-50 text-blue-700",
    verified: "bg-green-50 text-green-700",
    rejected: "bg-red-50 text-red-700",
    published: "bg-purple-50 text-purple-700",
  };
  return <Badge className={styles[status]}>{status}</Badge>;
}

function PassFailPill({ passFail }: { passFail: PassFail }) {
  return (
    <Badge className={passFail === "Passed" ? "bg-green-600 text-white" : "bg-amber-600 text-white"}>
      {passFail}
    </Badge>
  );
}
