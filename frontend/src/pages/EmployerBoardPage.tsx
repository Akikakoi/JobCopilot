import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Candidate, Job } from "../lib/types";
import { Button, Card, EmptyState, Modal, ProgressBar, ScoreRing, Skeleton, cn } from "../components/ui";
import { DuelModal } from "../components/DuelModal";
import { InterviewReportModal } from "../components/InterviewReportModal";

const COLUMNS: Array<{ key: string; label: string; accent: string }> = [
  { key: "submitted", label: "已投递", accent: "bg-slate-400" },
  { key: "screening", label: "筛选中", accent: "bg-primary" },
  { key: "interview", label: "面试中", accent: "bg-warning" },
  { key: "offer", label: "已录用", accent: "bg-success" },
  { key: "rejected", label: "未通过", accent: "bg-danger" },
];

interface JobWithCount extends Job {
  applicant_count: number;
}

function CandidateCard({
  candidate,
  onOpen,
  onDragStart,
  dragging,
}: {
  candidate: Candidate;
  onOpen: () => void;
  onDragStart: () => void;
  dragging: boolean;
}) {
  return (
    <div
      draggable
      onDragStart={(event) => {
        event.dataTransfer.setData("text/plain", String(candidate.application_id));
        event.dataTransfer.effectAllowed = "move";
        onDragStart();
      }}
      onClick={onOpen}
      className={cn(
        "cursor-grab rounded-xl border border-line bg-white p-3 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md active:cursor-grabbing",
        dragging && "drag-ghost",
      )}
      style={{ transitionTimingFunction: "var(--ease-out)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{candidate.candidate_name}</p>
          <p className="mt-0.5 text-[11px] text-muted">
            {candidate.structured.title} · {candidate.structured.years_of_experience} 年
          </p>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-lg px-2 py-0.5 text-xs font-semibold tabular-nums",
            candidate.match_score >= 80
              ? "bg-[#EAF8F0] text-success"
              : candidate.match_score >= 60
                ? "bg-[#EEF3FF] text-primary"
                : "bg-[#FDF3E7] text-warning",
          )}
        >
          {Math.round(candidate.match_score)}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {(candidate.structured.skills || []).slice(0, 3).map((skill) => (
          <span key={skill} className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
            {skill}
          </span>
        ))}
      </div>
      {candidate.breakdown.skills_required.missing && candidate.breakdown.skills_required.missing.length > 0 && (
        <p className="mt-1.5 truncate text-[10px] text-warning">
          缺 {candidate.breakdown.skills_required.missing.slice(0, 2).join("、")}
        </p>
      )}
    </div>
  );
}

export function EmployerBoardPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [duelCandidate, setDuelCandidate] = useState<Candidate | null>(null);
  const [interviewCandidate, setInterviewCandidate] = useState<Candidate | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["my-jobs"],
    queryFn: () => api.get<{ items: JobWithCount[] }>("/jobs/mine"),
  });

  const jobId = Number(searchParams.get("jobId") || jobsQuery.data?.items[0]?.id || 0);

  useEffect(() => {
    if (!searchParams.get("jobId") && jobsQuery.data?.items[0]) {
      setSearchParams({ jobId: String(jobsQuery.data.items[0].id) }, { replace: true });
    }
  }, [jobsQuery.data, searchParams, setSearchParams]);

  const candidatesQuery = useQuery({
    queryKey: ["candidates", jobId],
    queryFn: () => api.get<{ items: Candidate[] }>(`/match/job/${jobId}/candidates`),
    enabled: Boolean(jobId),
  });

  const currentJob = useMemo(
    () => jobsQuery.data?.items.find((job) => job.id === jobId),
    [jobsQuery.data, jobId],
  );

  const patchMutation = useMutation({
    mutationFn: ({ applicationId, status }: { applicationId: number; status: string }) =>
      api.patch(`/applications/${applicationId}/status`, { status }),
    onMutate: async ({ applicationId, status }) => {
      await queryClient.cancelQueries({ queryKey: ["candidates", jobId] });
      const previous = queryClient.getQueryData<{ items: Candidate[] }>(["candidates", jobId]);
      queryClient.setQueryData<{ items: Candidate[] }>(["candidates", jobId], (old) =>
        old
          ? {
              items: old.items.map((item) =>
                item.application_id === applicationId ? { ...item, status } : item,
              ),
            }
          : old,
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["candidates", jobId], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
      queryClient.invalidateQueries({ queryKey: ["my-jobs"] });
    },
  });

  const handleDrop = (status: string, event: React.DragEvent) => {
    event.preventDefault();
    setDropTarget(null);
    setDraggingId(null);
    const applicationId = Number(event.dataTransfer.getData("text/plain"));
    if (!applicationId) return;
    const candidate = candidatesQuery.data?.items.find((item) => item.application_id === applicationId);
    if (!candidate || candidate.status === status) return;
    patchMutation.mutate({ applicationId, status });
  };

  const grouped = useMemo(() => {
    const map: Record<string, Candidate[]> = {};
    COLUMNS.forEach((column) => (map[column.key] = []));
    (candidatesQuery.data?.items || []).forEach((candidate) => {
      (map[candidate.status] ||= []).push(candidate);
    });
    return map;
  }, [candidatesQuery.data]);

  return (
    <div className="flex h-full flex-col px-4 py-6 md:px-8">
      <header className="flex flex-wrap items-end justify-between gap-3 animate-fade-up">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Candidate Board</p>
          <h1 className="mt-1.5 text-[26px] font-semibold tracking-tight">候选人看板</h1>
          <p className="mt-1 text-sm text-muted">按匹配分排序，拖拽卡片即可推进流程状态。</p>
        </div>

        <div className="flex items-center gap-2">
          <select
            className="input w-[260px]"
            value={jobId || ""}
            onChange={(event) => setSearchParams({ jobId: event.target.value })}
          >
            {(jobsQuery.data?.items || []).map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}（{job.applicant_count} 份投递）
              </option>
            ))}
          </select>
        </div>
      </header>

      {currentJob && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-white px-4 py-3 text-xs text-muted animate-fade-in">
          <span className="font-medium text-ink">{currentJob.title}</span>
          <span>
            {currentJob.location} · {currentJob.experience_min}-{currentJob.experience_max} 年 ·{" "}
            {currentJob.salary_min}-{currentJob.salary_max}K
          </span>
          <span className="ml-auto">
            共 {candidatesQuery.data?.items.length || 0} 位候选人
          </span>
        </div>
      )}

      {jobsQuery.isLoading || candidatesQuery.isLoading ? (
        <div className="mt-5 grid flex-1 grid-cols-2 gap-3 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-64 w-full" />
          ))}
        </div>
      ) : !jobsQuery.data?.items.length ? (
        <div className="mt-6">
          <EmptyState title="还没有岗位" description="先去岗位管理发布一个岗位，再回来看候选人。" />
        </div>
      ) : (
        <div className="mt-5 grid flex-1 grid-cols-2 gap-3 overflow-y-auto pb-4 lg:grid-cols-5">
          {COLUMNS.map((column) => (
            <section
              key={column.key}
              onDragOver={(event) => {
                event.preventDefault();
                setDropTarget(column.key);
              }}
              onDragLeave={() => setDropTarget((prev) => (prev === column.key ? null : prev))}
              onDrop={(event) => handleDrop(column.key, event)}
              className={cn(
                "flex min-h-[240px] flex-col rounded-2xl border border-line bg-white/60 p-2.5 transition-colors",
                dropTarget === column.key && "drop-active",
              )}
              style={{ transitionDuration: "var(--dur-base)" }}
            >
              <div className="mb-2 flex items-center gap-2 px-1">
                <span className={cn("h-1.5 w-1.5 rounded-full", column.accent)} />
                <p className="text-xs font-semibold text-slate-600">{column.label}</p>
                <span className="ml-auto text-[10px] text-slate-400">{grouped[column.key]?.length || 0}</span>
              </div>
              <div className="space-y-2">
                {(grouped[column.key] || []).map((candidate) => (
                  <CandidateCard
                    key={candidate.application_id}
                    candidate={candidate}
                    dragging={draggingId === candidate.application_id}
                    onDragStart={() => setDraggingId(candidate.application_id)}
                    onOpen={() => setSelected(candidate)}
                  />
                ))}
                {!(grouped[column.key] || []).length && (
                  <div className="rounded-xl border border-dashed border-line/80 py-8 text-center text-[10px] text-slate-400">
                    拖到这里
                  </div>
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      <Modal
        open={Boolean(selected)}
        title={selected ? `候选人 · ${selected.candidate_name}` : ""}
        width="max-w-2xl"
        onClose={() => setSelected(null)}
        footer={
          selected ? (
            <div className="flex w-full flex-wrap items-center justify-between gap-2">
              <select
                className="input w-[160px]"
                value={selected.status}
                onChange={(event) => {
                  patchMutation.mutate({
                    applicationId: selected.application_id,
                    status: event.target.value,
                  });
                  setSelected({ ...selected, status: event.target.value });
                }}
              >
                {COLUMNS.map((column) => (
                  <option key={column.key} value={column.key}>
                    {column.label}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setInterviewCandidate(selected)}
                >
                  面试报告
                </Button>
                <Button variant="soft" size="sm" onClick={() => setDuelCandidate(selected)}>
                  AI 双方面谈
                </Button>
                <Button variant="ghost" onClick={() => setSelected(null)}>
                  关闭
                </Button>
              </div>
            </div>
          ) : null
        }
      >
        {selected && (
          <div className="space-y-4">
            <div className="flex items-center gap-5">
              <ScoreRing score={selected.match_score} size={104} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">{selected.structured.title}</p>
                <p className="mt-0.5 text-xs text-muted">
                  {selected.structured.years_of_experience} 年经验 · 期望{" "}
                  {selected.structured.expectations?.locations?.join("、") || "未填写"} ·{" "}
                  {selected.structured.expectations?.salary_min ?? "?"}-
                  {selected.structured.expectations?.salary_max ?? "?"}K
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {(selected.structured.skills || []).map((skill) => (
                    <span key={skill} className="chip">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <Card className="p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">规则分明细</p>
              <div className="mt-3 space-y-3">
                {[
                  ["必需技能", selected.breakdown.skills_required.score, 40],
                  ["加分技能", selected.breakdown.skills_preferred.score, 10],
                  ["工作年限", selected.breakdown.experience.score, 20],
                  ["地点", selected.breakdown.location.score, 15],
                  ["薪资", selected.breakdown.salary.score, 15],
                ].map(([label, score, max]) => (
                  <div key={String(label)}>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-600">{label}</span>
                      <span className="tabular-nums text-muted">
                        {score} / {max}
                      </span>
                    </div>
                    <div className="mt-1">
                      <ProgressBar value={Number(score)} max={Number(max)} />
                    </div>
                  </div>
                ))}
              </div>
            </Card>

            {selected.match_explanation ? (
              <div className="rounded-xl bg-[#F6F8FE] p-4">
                <p className="text-xs font-semibold text-primary">AI 评估</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-600">
                  {selected.match_explanation.summary}
                </p>
                {selected.match_explanation.gaps.length > 0 && (
                  <p className="mt-2 text-xs leading-relaxed text-slate-500">
                    差距：{selected.match_explanation.gaps.join("；")}
                  </p>
                )}
              </div>
            ) : (
              <div className="rounded-xl bg-[#F6F8FE] p-4 text-xs leading-relaxed text-slate-500">
                还没有 AI 深度评估。可以在「AI 招聘助手」里说：「详细评一下这位候选人」，助手会生成完整评估。
              </div>
            )}

            {selected.structured.work_experience?.length > 0 && (
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">工作经历</p>
                <div className="mt-2 space-y-2">
                  {selected.structured.work_experience.map((work, index) => (
                    <div key={index} className="rounded-xl border border-line p-3">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium">{work.company}</span>
                        <span className="text-slate-400">{work.period}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted">{work.role}</p>
                      <ul className="mt-1 space-y-0.5">
                        {work.highlights.map((item) => (
                          <li key={item} className="text-[11px] leading-relaxed text-slate-500">
                            · {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>

      <DuelModal
        open={Boolean(duelCandidate)}
        jobId={jobId}
        jobTitle={currentJob?.title || ""}
        applicationId={duelCandidate?.application_id || 0}
        candidateName={duelCandidate?.candidate_name || ""}
        onClose={() => setDuelCandidate(null)}
      />

      <InterviewReportModal
        open={Boolean(interviewCandidate)}
        applicationId={interviewCandidate?.application_id || 0}
        candidateName={interviewCandidate?.candidate_name || ""}
        onClose={() => setInterviewCandidate(null)}
      />
    </div>
  );
}
