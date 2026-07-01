import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { marked } from "marked";
import { toast, Toaster } from "sonner";
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Database,
  Loader2,
  MessageSquarePlus,
  XCircle,
} from "lucide-react";
import { AdminJudgeSidebar } from "@/components/admin-judge-sidebar";
import { ReviewerRubricPanel } from "@/components/reviewer-rubric-panel";
import { useAuth } from "@/contexts/AuthContext";
import {
  fetchJudge,
  fetchNotes,
  fetchPortalConfig,
  fetchReviewerScores,
  fetchUnit,
  patchStatus,
  postNote,
  postReviewerRubric,
  publishToDynamoDB,
  rejectUnit,
} from "@/lib/api";
import {
  mapJudgeReport,
  mapReviewerNote,
  mapReviewerScore,
  mapUnitDetail,
} from "@/lib/mappers";
import type {
  JudgeReportUi,
  PassFail,
  ReviewerNote,
  ReviewerScoreUi,
  RubricDraft,
  Status,
  UnitDetail,
} from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";
import { Dialog } from "./ui/dialog";
import { ScrollArea } from "./ui/scroll-area";
import { Separator } from "./ui/separator";
import { Textarea } from "./ui/textarea";

const DEFAULT_RUBRIC: RubricDraft = {
  representation: 7,
  engagement: 7,
  actionExpression: 7,
  notes: "",
};

export function UnitReview() {
  const { unitId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [unit, setUnit] = useState<UnitDetail | null>(null);
  const [judge, setJudge] = useState<JudgeReportUi | null>(null);
  const [reviewerScores, setReviewerScores] = useState<ReviewerScoreUi[]>([]);
  const [notes, setNotes] = useState<ReviewerNote[]>([]);
  const [rubricDraft, setRubricDraft] = useState<RubricDraft>(DEFAULT_RUBRIC);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [approveOpen, setApproveOpen] = useState(false);
  const [adminApproveOpen, setAdminApproveOpen] = useState(false);
  const [sendBackOpen, setSendBackOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectNoteText, setRejectNoteText] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [objectivesOpen, setObjectivesOpen] = useState(true);
  const [acting, setActing] = useState(false);
  const [lessonHtml, setLessonHtml] = useState("");
  const [publishEnabled, setPublishEnabled] = useState(false);

  const load = useCallback(async () => {
    if (!unitId || !user) return;
    setLoading(true);
    setError("");
    try {
      const detail = await fetchUnit(unitId);
      setUnit(mapUnitDetail(detail));

      if (user.role === "admin") {
        const [judgeRaw, notesRaw, scoresRaw] = await Promise.all([
          fetchJudge(unitId),
          fetchNotes(unitId),
          fetchReviewerScores(unitId),
        ]);
        setJudge(mapJudgeReport(judgeRaw));
        setNotes(notesRaw.map(mapReviewerNote));
        setReviewerScores(scoresRaw.map(mapReviewerScore));
      } else {
        setJudge(null);
        const notesRaw = await fetchNotes(unitId);
        setNotes(notesRaw.map(mapReviewerNote));
        setReviewerScores([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load unit");
    } finally {
      setLoading(false);
    }
  }, [unitId, user]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    // Admin-only feature flag — but the endpoint is accessible to any signed-in
    // user so the read is cheap and avoids a role-conditional fetch.
    let cancelled = false;
    fetchPortalConfig()
      .then((cfg) => {
        if (!cancelled) setPublishEnabled(cfg.publish_enabled);
      })
      .catch(() => {
        // Treat fetch failure as "flag off" so the UI stays in the safe path.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!unit?.lessonBody) {
      setLessonHtml("");
      return;
    }
    const parsed = marked.parse(unit.lessonBody);
    if (typeof parsed === "string") {
      setLessonHtml(parsed);
    } else {
      void parsed.then((html) => setLessonHtml(html));
    }
  }, [unit?.lessonBody]);

  if (!user) {
    navigate("/");
    return null;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-neutral-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading unit…
      </div>
    );
  }

  if (error || !unit || (isAdmin && !judge)) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <p className="text-red-600">{error || "Unit not found"}</p>
        <Button variant="outline" onClick={() => navigate("/queue")}>
          Back to queue
        </Button>
      </div>
    );
  }

  const handleReviewerApprove = async () => {
    if (!user) return;
    setActing(true);
    try {
      await postReviewerRubric(unit.id, {
        representation: rubricDraft.representation,
        engagement: rubricDraft.engagement,
        action_expression: rubricDraft.actionExpression,
        notes: rubricDraft.notes,
        checked_by: user.email,
        mark_verified: true,
      });
      setApproveOpen(false);
      toast.success("Review submitted", {
        description: "Your rubric scores were saved and the unit is marked verified",
      });
      navigate("/queue");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Submit failed");
    } finally {
      setActing(false);
    }
  };

  const handleAdminApprove = async () => {
    setActing(true);
    try {
      if (publishEnabled) {
        // Atomically: DynamoDB write + Postgres status flip. Server is the
        // source of truth on the flag — even if the SPA cache says ON, the
        // server returns 503 when actually OFF (e.g. flag flipped mid-session)
        // and we fall through to the catch block.
        await publishToDynamoDB(unit.id);
        toast.success("Unit published to DynamoDB", {
          description: "Postgres status set to published",
        });
      } else {
        await patchStatus(unit.id, "published");
        toast.success("Unit marked published", {
          description: "Postgres-only (DynamoDB publish disabled)",
        });
      }
      setAdminApproveOpen(false);
      navigate("/queue");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    } finally {
      setActing(false);
    }
  };

  const handleSendBack = async () => {
    setActing(true);
    try {
      await patchStatus(unit.id, "draft");
      setSendBackOpen(false);
      toast.success("Sent back to draft");
      navigate("/queue");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    } finally {
      setActing(false);
    }
  };

  const handleReject = async () => {
    const note = rejectNoteText.trim();
    if (!note) return;
    setActing(true);
    try {
      await rejectUnit(unit.id, note);
      setRejectOpen(false);
      setRejectNoteText("");
      toast.success("Unit rejected", {
        description: "Reason recorded in the unit's review history",
      });
      navigate("/queue");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setActing(false);
    }
  };

  const handleSaveNote = async () => {
    if (!noteText.trim() || !user) return;
    setActing(true);
    try {
      await postNote(unit.id, noteText.trim(), user.email);
      setNoteOpen(false);
      setNoteText("");
      toast.success("Note saved");
      const notesRaw = await fetchNotes(unit.id);
      setNotes(notesRaw.map(mapReviewerNote));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save note");
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50">
      <Toaster richColors position="top-center" />
      <header className="sticky top-0 z-10 border-b bg-white">
        <div className="flex items-center justify-between gap-4 px-6 py-4">
          <div className="flex min-w-0 flex-1 items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/queue")}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to queue
            </Button>
            <Separator orientation="vertical" className="h-6" />
            <div className="flex min-w-0 flex-wrap items-center gap-3">
              <code className="truncate font-mono text-sm text-neutral-700">{unit.id}</code>
              <StatusBadge status={unit.status} />
              {isAdmin && judge && (
                <JudgeChip score={judge.overallScore} passFail={judge.passFail} />
              )}
              {isAdmin && reviewerScores.length > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {reviewerScores.length} reviewer score
                  {reviewerScores.length === 1 ? "" : "s"}
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setNoteOpen(true)}>
              <MessageSquarePlus className="mr-2 h-4 w-4" />
              Add note
            </Button>
            <Button variant="outline" size="sm" onClick={() => setSendBackOpen(true)} disabled={acting}>
              Send back to draft
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRejectOpen(true)}
              disabled={acting || unit.status === "rejected"}
              className="text-red-700 hover:bg-red-50 hover:text-red-800"
            >
              <XCircle className="mr-2 h-4 w-4" />
              Reject
            </Button>
            {!isAdmin && (
              <Button size="sm" onClick={() => setApproveOpen(true)} disabled={acting}>
                Submit review
              </Button>
            )}
            {isAdmin && (
              <Button size="sm" onClick={() => setAdminApproveOpen(true)} disabled={acting}>
                <Database className="mr-2 h-4 w-4" />
                Approve & publish
              </Button>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1440px]">
        <div className="grid gap-0 lg:grid-cols-[1fr_560px]">
          <LessonColumn
            unit={unit}
            lessonHtml={lessonHtml}
            objectivesOpen={objectivesOpen}
            onObjectivesOpenChange={setObjectivesOpen}
          />
          <div className="bg-neutral-50">
            <ScrollArea className="h-[calc(100vh-73px)]">
              <div className="p-6">
                {isAdmin && judge ? (
                  <AdminJudgeSidebar
                    judge={judge}
                    reviewerScores={reviewerScores}
                    notes={notes}
                  />
                ) : (
                  <ReviewerRubricPanel draft={rubricDraft} onChange={setRubricDraft} />
                )}
              </div>
            </ScrollArea>
          </div>
        </div>
      </div>

      <Dialog
        open={approveOpen}
        title="Submit your review?"
        description="Your UDL rubric scores will be saved and this unit will be marked verified for admin approval."
        onClose={() => setApproveOpen(false)}
        footer={
          <>
            <Button variant="outline" onClick={() => setApproveOpen(false)} disabled={acting}>
              Cancel
            </Button>
            <Button onClick={handleReviewerApprove} disabled={acting}>
              Submit review
            </Button>
          </>
        }
      />

      <Dialog
        open={adminApproveOpen}
        title="Approve and publish?"
        description={
          publishEnabled
            ? "This writes the unit to DynamoDB and sets Postgres status to published in one atomic step."
            : "This sets status to published in Postgres only. DynamoDB publishing is currently disabled (PORTAL_PUBLISH_ENABLED=false)."
        }
        onClose={() => setAdminApproveOpen(false)}
        footer={
          <>
            <Button variant="outline" onClick={() => setAdminApproveOpen(false)} disabled={acting}>
              Cancel
            </Button>
            <Button onClick={handleAdminApprove} disabled={acting}>
              Approve & publish
            </Button>
          </>
        }
      />

      <Dialog
        open={sendBackOpen}
        title="Send back to draft?"
        description="The unit will return to draft for pipeline or editorial follow-up."
        onClose={() => setSendBackOpen(false)}
        footer={
          <>
            <Button variant="outline" onClick={() => setSendBackOpen(false)} disabled={acting}>
              Cancel
            </Button>
            <Button onClick={handleSendBack} disabled={acting}>
              Send back
            </Button>
          </>
        }
      />

      <Dialog
        open={rejectOpen}
        title="Reject this unit?"
        description="The unit will be marked rejected and the reason will be recorded in its review history. A note is required."
        onClose={() => {
          setRejectOpen(false);
          setRejectNoteText("");
        }}
        footer={
          <>
            <Button
              variant="outline"
              onClick={() => {
                setRejectOpen(false);
                setRejectNoteText("");
              }}
              disabled={acting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleReject}
              disabled={acting || !rejectNoteText.trim()}
              className="bg-red-600 hover:bg-red-700"
            >
              Reject unit
            </Button>
          </>
        }
      >
        <Textarea
          placeholder="Reason for rejection — what needs to change before this unit can be reviewed again?"
          value={rejectNoteText}
          onChange={(e) => setRejectNoteText(e.target.value)}
          rows={6}
          autoFocus
        />
      </Dialog>

      <Dialog
        open={noteOpen}
        title="Reviewer note"
        onClose={() => setNoteOpen(false)}
        footer={
          <>
            <Button variant="outline" onClick={() => setNoteOpen(false)} disabled={acting}>
              Cancel
            </Button>
            <Button onClick={handleSaveNote} disabled={acting || !noteText.trim()}>
              Save note
            </Button>
          </>
        }
      >
        <Textarea
          placeholder="Document issues, approval rationale, or follow-ups..."
          value={noteText}
          onChange={(e) => setNoteText(e.target.value)}
          rows={6}
        />
      </Dialog>
    </div>
  );
}

function LessonColumn({
  unit,
  lessonHtml,
  objectivesOpen,
  onObjectivesOpenChange,
}: {
  unit: UnitDetail;
  lessonHtml: string;
  objectivesOpen: boolean;
  onObjectivesOpenChange: (open: boolean) => void;
}) {
  return (
    <div className="border-r bg-white">
      <ScrollArea className="h-[calc(100vh-73px)]">
        <div className="max-w-3xl px-8 py-8">
          <div className="mb-8">
            <h1 className="mb-3 text-3xl font-semibold text-neutral-900">{unit.title}</h1>
            <p className="mb-4 text-sm text-neutral-600">
              {unit.className} · {unit.theme} · {unit.topic}
            </p>
            <Collapsible open={objectivesOpen} onOpenChange={onObjectivesOpenChange}>
              <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-neutral-700 hover:text-neutral-900">
                Learning objectives
                {objectivesOpen ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-3">
                <ul className="list-disc space-y-2 pl-5 text-sm text-neutral-700">
                  {unit.learningObjectives.map((obj, i) => (
                    <li key={i}>{obj}</li>
                  ))}
                </ul>
              </CollapsibleContent>
            </Collapsible>
          </div>

          <Separator className="mb-8" />

          <article
            className="prose prose-neutral max-w-none"
            dangerouslySetInnerHTML={{ __html: lessonHtml }}
          />

          {unit.figures.length > 0 && (
            <div className="mt-10">
              <h3 className="mb-4 text-lg font-medium">Figures</h3>
              <div className="grid gap-4 md:grid-cols-2">
                {unit.figures.map((figure) => (
                  <div key={figure.id} className="overflow-hidden rounded-lg border bg-white">
                    {figure.thumbnail ? (
                      <img
                        src={figure.thumbnail}
                        alt={figure.altText}
                        className="h-48 w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-48 items-center justify-center bg-neutral-100 text-sm text-neutral-500">
                        No preview
                      </div>
                    )}
                    <div className="p-4">
                      <Badge variant="secondary" className="mb-2 text-xs">
                        {figure.source}
                      </Badge>
                      <p className="mb-1 text-sm font-medium">{figure.caption}</p>
                      <p className="text-xs text-neutral-600">Alt: {figure.altText}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-12 space-y-1 border-t pt-6 text-xs text-neutral-500">
            <p>Last updated: {unit.lastUpdated}</p>
            <p>{unit.modelVersion}</p>
            <p>Prompt: {unit.promptVersion}</p>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

function StatusBadge({ status }: { status: Status }) {
  const variants: Record<Status, { label: string; className: string }> = {
    draft: { label: "Draft", className: "bg-neutral-100 text-neutral-700" },
    draft_curriculum_only: {
      label: "Draft (curriculum)",
      className: "bg-blue-50 text-blue-700",
    },
    verified: { label: "Verified", className: "bg-green-50 text-green-700" },
    rejected: { label: "Rejected", className: "bg-red-50 text-red-700" },
    published: { label: "Published", className: "bg-purple-50 text-purple-700" },
  };
  const variant = variants[status];
  return (
    <Badge variant="secondary" className={variant.className}>
      {variant.label}
    </Badge>
  );
}

function JudgeChip({ score, passFail }: { score: number; passFail: PassFail }) {
  return (
    <div className="flex items-center gap-2 rounded-full bg-neutral-100 px-3 py-1">
      <span className="text-sm font-medium">{score.toFixed(1)}/10 LLM</span>
      <span className="text-neutral-400">·</span>
      <span
        className={`text-sm font-medium ${
          passFail === "Passed" ? "text-green-700" : "text-amber-700"
        }`}
      >
        {passFail}
      </span>
    </div>
  );
}
