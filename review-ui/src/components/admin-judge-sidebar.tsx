import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Users } from "lucide-react";
import type {
  CheckpointSort,
  CheckpointUi,
  JudgeReportUi,
  PassFail,
  ReviewerNote,
  ReviewerScoreUi,
} from "@/lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "./ui/collapsible";
import { Progress } from "./ui/progress";
import { Separator } from "./ui/separator";

export function AdminJudgeSidebar({
  judge,
  reviewerScores,
  notes,
}: {
  judge: JudgeReportUi;
  reviewerScores: ReviewerScoreUi[];
  notes: ReviewerNote[];
}) {
  const [correctnessOpen, setCorrectnessOpen] = useState(false);
  const [clarityOpen, setClarityOpen] = useState(false);
  const [checkpointSort, setCheckpointSort] = useState<CheckpointSort>("default");
  const [showAllCheckpoints, setShowAllCheckpoints] = useState(false);

  const sortedCheckpoints = useMemo(
    () => sortCheckpoints(judge.checkpoints, checkpointSort),
    [judge.checkpoints, checkpointSort],
  );

  const visibleCheckpoints = showAllCheckpoints
    ? sortedCheckpoints
    : sortedCheckpoints.slice(0, 4);

  const reviewers = [...new Set(reviewerScores.map((s) => s.reviewer))];

  return (
    <div className="space-y-6">
      {reviewers.length > 0 && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-green-900">
            <Users className="h-4 w-4" />
            Reviewed by
          </div>
          <div className="flex flex-wrap gap-2">
            {reviewers.map((email) => (
              <Badge key={email} className="bg-white text-green-800">
                {email}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border bg-white p-6">
        <h2 className="mb-1 text-sm font-medium text-neutral-600">LLM UDL judge report</h2>
        <p className="mb-4 text-xs text-neutral-500">Automated evaluation (not shown to reviewers)</p>
        <div className="mb-4 flex items-baseline gap-2">
          <span className="text-4xl font-semibold">{judge.overallScore.toFixed(1)}</span>
          <span className="text-lg text-neutral-500">/ 10</span>
          <PassFailPill passFail={judge.passFail} />
        </div>
        <div className="mb-6 space-y-3">
          <PrincipleScore label="Representation" score={judge.principles.representation} />
          <PrincipleScore label="Engagement" score={judge.principles.engagement} />
          <PrincipleScore label="Action & Expression" score={judge.principles.actionExpression} />
        </div>
        <Separator className="my-6" />
        <div className="space-y-4">
          <QualityCollapsible
            label="Correctness"
            score={judge.quality.correctness}
            notes={judge.quality.correctnessNotes}
            open={correctnessOpen}
            onOpenChange={setCorrectnessOpen}
          />
          <QualityCollapsible
            label="Clarity"
            score={judge.quality.clarity}
            notes={judge.quality.clarityNotes}
            open={clarityOpen}
            onOpenChange={setClarityOpen}
          />
        </div>
      </div>

      <div className="rounded-lg border bg-white p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-medium">Checkpoint scores</h3>
          <select
            className="h-8 rounded-md border px-2 text-xs"
            value={checkpointSort}
            onChange={(e) => setCheckpointSort(e.target.value as CheckpointSort)}
          >
            <option value="default">Default order</option>
            <option value="score-desc">Score: high → low</option>
            <option value="score-asc">Score: low → high</option>
          </select>
        </div>
        <div className="space-y-3">
          {visibleCheckpoints.map((checkpoint) => (
            <CheckpointRow key={checkpoint.id} checkpoint={checkpoint} />
          ))}
        </div>
        {!showAllCheckpoints && sortedCheckpoints.length > 4 && (
          <Button
            variant="ghost"
            size="sm"
            className="mt-3 w-full"
            onClick={() => setShowAllCheckpoints(true)}
          >
            Show all {sortedCheckpoints.length} checkpoints
          </Button>
        )}
      </div>

      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-4 text-sm font-medium">LLM recommendations</h3>
        {judge.recommendations.length === 0 ? (
          <p className="text-sm text-neutral-500">No recommendations</p>
        ) : (
          <ul className="space-y-2">
            {judge.recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm text-neutral-700">
                <span className="text-neutral-400">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-4 text-sm font-medium">Reviewer scores</h3>
        {reviewerScores.length === 0 ? (
          <p className="text-sm text-neutral-500">No human rubric submissions yet</p>
        ) : (
          <div className="space-y-4">
            {reviewerScores.map((score) => (
              <ReviewerScoreCard key={score.id} score={score} />
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-4 text-sm font-medium">Reviewer notes</h3>
        {notes.length === 0 ? (
          <p className="text-sm text-neutral-500">No reviewer notes yet</p>
        ) : (
          <div className="space-y-4">
            {notes.map((note, i) => (
              <div key={i} className="border-l-2 pl-3">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-xs font-medium">{note.author}</span>
                  <span className="text-xs text-neutral-500">{note.date}</span>
                </div>
                <p className="text-sm text-neutral-700">{note.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function sortCheckpoints(items: CheckpointUi[], sort: CheckpointSort): CheckpointUi[] {
  const copy = [...items];
  if (sort === "score-desc") return copy.sort((a, b) => b.score - a.score);
  if (sort === "score-asc") return copy.sort((a, b) => a.score - b.score);
  return copy;
}

function ReviewerScoreCard({ score }: { score: ReviewerScoreUi }) {
  return (
    <div className="rounded-md border bg-neutral-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{score.reviewer}</span>
        <span className="text-xs text-neutral-500">{score.date}</span>
      </div>
      <div className="mb-2 flex items-baseline gap-2">
        <span className="text-2xl font-semibold">{score.overallScore.toFixed(1)}</span>
        <span className="text-sm text-neutral-500">/ 10 avg</span>
      </div>
      <div className="space-y-2 text-xs">
        <ScoreLine label="Representation" value={score.representation} />
        <ScoreLine label="Engagement" value={score.engagement} />
        <ScoreLine label="Action & Expression" value={score.actionExpression} />
      </div>
      {score.notes && (
        <p className="mt-3 border-t pt-3 text-sm text-neutral-700">{score.notes}</p>
      )}
    </div>
  );
}

function ScoreLine({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between">
      <span className="text-neutral-600">{label}</span>
      <span className="font-medium tabular-nums">{value.toFixed(1)}</span>
    </div>
  );
}

function CheckpointRow({ checkpoint }: { checkpoint: CheckpointUi }) {
  return (
    <div className="flex items-start gap-3 border-b pb-3 text-sm last:border-0">
      <code className="mt-0.5 font-mono text-xs text-neutral-500">{checkpoint.id}</code>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-xs text-neutral-600">{checkpoint.principle}</span>
          <span className="font-medium">{checkpoint.score.toFixed(1)}</span>
        </div>
        <p className="text-xs text-neutral-600">{checkpoint.notes}</p>
      </div>
    </div>
  );
}

function QualityCollapsible({
  label,
  score,
  notes,
  open,
  onOpenChange,
}: {
  label: string;
  score: number;
  notes: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{label}</span>
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{score.toFixed(1)}</span>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm">
              {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </CollapsibleTrigger>
        </div>
      </div>
      <CollapsibleContent className="mt-2">
        <p className="text-xs text-neutral-600">{notes}</p>
      </CollapsibleContent>
    </Collapsible>
  );
}

function PassFailPill({ passFail }: { passFail: PassFail }) {
  return (
    <Badge
      className={
        passFail === "Passed"
          ? "bg-green-600 text-white hover:bg-green-700"
          : "bg-amber-600 text-white hover:bg-amber-700"
      }
    >
      {passFail}
    </Badge>
  );
}

function PrincipleScore({ label, score }: { label: string; score: number }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-sm">
        <span className="text-neutral-700">{label}</span>
        <span className="font-medium">{score.toFixed(1)}</span>
      </div>
      <Progress value={score * 10} className="h-2" />
    </div>
  );
}
