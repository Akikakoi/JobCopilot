import type { Interview } from "../lib/types";
import { Badge, Card, ProgressBar, ScoreRing } from "./ui";

const DIMENSION_LABELS: Array<[string, string]> = [
  ["skills", "技能匹配"],
  ["project", "项目深度"],
  ["communication", "表达沟通"],
  ["motivation", "求职动机"],
];

const CATEGORY_LABELS: Record<string, string> = {
  technical: "技术",
  project: "项目",
  behavior: "行为",
};

function toneFor(score: number) {
  return score >= 80 ? "success" : score >= 60 ? "primary" : "warning";
}

export function InterviewReportView({ interview }: { interview: Interview }) {
  const report = interview.report;
  if (!report) {
    return <p className="text-sm text-muted">暂无面试报告。</p>;
  }
  const answerMap = new Map(interview.answers.map((item) => [item.question_id, item]));
  const perQuestion = new Map(
    (report.per_question || []).map((item) => [item.question_id, item]),
  );

  return (
    <div className="space-y-4">
      <Card className="p-6">
        <div className="flex flex-wrap items-center gap-6">
          <ScoreRing score={report.overall_score} label="面试总分" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">
              {interview.job_title}
              <span className="ml-1.5 font-normal text-muted">· {interview.company_name}</span>
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted">{report.summary}</p>
            <div className="mt-4 space-y-2.5">
              {DIMENSION_LABELS.map(([key, label]) => (
                <div key={key}>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-600">{label}</span>
                    <span className="tabular-nums text-muted">{report.dimensions[key] ?? 0}</span>
                  </div>
                  <div className="mt-1">
                    <ProgressBar
                      value={report.dimensions[key] ?? 0}
                      max={100}
                      tone={toneFor(report.dimensions[key] ?? 0)}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-success">亮点</p>
          <ul className="mt-2 space-y-1.5">
            {report.strengths.length ? (
              report.strengths.map((item) => (
                <li key={item} className="flex gap-2 text-xs leading-relaxed text-slate-600">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-success" />
                  {item}
                </li>
              ))
            ) : (
              <li className="text-xs text-muted">暂无</li>
            )}
          </ul>
        </Card>
        <Card className="p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-warning">风险</p>
          <ul className="mt-2 space-y-1.5">
            {report.risks.length ? (
              report.risks.map((item) => (
                <li key={item} className="flex gap-2 text-xs leading-relaxed text-slate-600">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-warning" />
                  {item}
                </li>
              ))
            ) : (
              <li className="text-xs text-muted">暂无</li>
            )}
          </ul>
        </Card>
      </div>

      <Card className="p-5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-primary">改进建议</p>
        <ul className="mt-2 space-y-1.5">
          {report.suggestions.length ? (
            report.suggestions.map((item) => (
              <li key={item} className="flex gap-2 text-xs leading-relaxed text-slate-600">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                {item}
              </li>
            ))
          ) : (
            <li className="text-xs text-muted">暂无</li>
          )}
        </ul>
      </Card>

      <Card className="p-5">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">逐题复盘</p>
        <div className="mt-3 space-y-3">
          {interview.plan.questions.map((question, index) => {
            const answer = answerMap.get(question.id);
            const scored = perQuestion.get(question.id);
            const score = scored?.score ?? answer?.score ?? 0;
            return (
              <div key={question.id} className="rounded-xl border border-line p-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400">Q{index + 1}</span>
                  <Badge tone="default">{CATEGORY_LABELS[question.category] || question.category}</Badge>
                  <span className="flex-1" />
                  <Badge tone={toneFor(score)}>{Math.round(score)} 分</Badge>
                </div>
                <p className="mt-1.5 text-xs font-medium leading-relaxed text-ink">{question.question}</p>
                {answer?.answer && (
                  <p className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-2.5 text-[11px] leading-relaxed text-slate-600">
                    {answer.answer}
                  </p>
                )}
                {(scored?.rationale || answer?.rationale) && (
                  <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
                    点评：{scored?.rationale || answer?.rationale}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
