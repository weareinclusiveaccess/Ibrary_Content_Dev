import type { RubricDraft } from "@/lib/types";
import { Textarea } from "./ui/textarea";

const PRINCIPLES: {
  key: keyof Pick<RubricDraft, "representation" | "engagement" | "actionExpression">;
  label: string;
  hint: string;
}[] = [
  {
    key: "representation",
    label: "Representation",
    hint: "Options for perception, language, and comprehension",
  },
  {
    key: "engagement",
    label: "Engagement",
    hint: "Interest, effort, and self-regulation",
  },
  {
    key: "actionExpression",
    label: "Action & Expression",
    hint: "Physical action, expression, and executive function",
  },
];

export function ReviewerRubricPanel({
  draft,
  onChange,
  readOnly = false,
}: {
  draft: RubricDraft;
  onChange: (draft: RubricDraft) => void;
  readOnly?: boolean;
}) {
  const overall =
    (draft.representation + draft.engagement + draft.actionExpression) / 3;

  return (
    <div className="space-y-6">
      <div className="rounded-lg border bg-white p-6">
        <h2 className="mb-1 text-sm font-medium text-neutral-900">Human review rubric</h2>
        <p className="mb-6 text-xs text-neutral-600">
          Score each UDL principle from 1 (needs work) to 10 (excellent). Your scores are
          separate from the automated LLM judge (visible to admins only).
        </p>
        <div className="mb-4 flex items-baseline gap-2">
          <span className="text-3xl font-semibold">{overall.toFixed(1)}</span>
          <span className="text-neutral-500">/ 10 average</span>
        </div>
        <div className="divide-y divide-neutral-200">
          {PRINCIPLES.map(({ key, label, hint }) => (
            <RubricSlider
              key={key}
              label={label}
              hint={hint}
              value={draft[key]}
              disabled={readOnly}
              onChange={(v) => onChange({ ...draft, [key]: v })}
            />
          ))}
        </div>
      </div>
      <div className="rounded-lg border bg-white p-6">
        <h3 className="mb-2 text-sm font-medium">Review notes (optional)</h3>
        <Textarea
          placeholder="Rationale, issues to fix, or approval comments…"
          value={draft.notes}
          onChange={(e) => onChange({ ...draft, notes: e.target.value })}
          rows={5}
          disabled={readOnly}
        />
      </div>
    </div>
  );
}

function RubricSlider({
  label,
  hint,
  value,
  onChange,
  disabled,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="border-0 py-5 first:pt-0 last:pb-0">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <span className="text-sm font-medium text-neutral-800">{label}</span>
          <p className="text-xs text-neutral-500">{hint}</p>
        </div>
        <span className="text-sm font-semibold tabular-nums">{value.toFixed(1)}</span>
      </div>
      <input
        type="range"
        min={1}
        max={10}
        step={0.5}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-neutral-900"
      />
    </div>
  );
}
