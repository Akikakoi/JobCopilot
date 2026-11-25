import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, fetchBlob } from "../lib/api";
import type { Candidate, Job } from "../lib/types";
import { DownloadIcon } from "../components/icons";
import { Badge, Button, EmptyState, Modal, ProgressBar, ScoreRing, Select, Skeleton, STATUS_META, Textarea, cn } from "../components/ui";
import { DuelModal } from "../components/DuelModal";
import { InterviewReportModal } from "../components/InterviewReportModal";
import { EmployerPipeline } from "../components/PipelinePanel";

const COLUMNS: Array<{ key: string; label: string; accent: string }> = [
  { key: "submitted", label: "已投递", accent: "bg-muted" },
  { key: "screening", label: "筛选中", accent: "bg-primary" },
  { key: "interview", label: "面试中", accent: "bg-warning" },
  { key: "offer", label: "Offer 阶段", accent: "bg-success" },
  { key: "onboarding", label: "待入职", accent: "bg-primary" },
  { key: "hired", label: "已入职", accent: "bg-success" },
  { key: "abandoned", label: "放弃入职", accent: "bg-muted" },
  { key: "rejected", label: "未通过", accent: "bg-danger" },
];

// 入职阶段由双端入职动作驱动；Offer 由「发起 Offer」驱动，看板只允许从 offer 收尾为未通过
const GENERIC_STAGE_ORDER = ["submitted", "screening", "interview"];
const DRAGGABLE_STATUSES = new Set(["submitted", "screening", "interview", "offer"]);
const DROP_TARGET_STATUSES = new Set(["screening", "interview", "rejected"]);

function statusTargets(current: string): string[] {
  if (current === "offer") return ["rejected"];
  const index = GENERIC_STAGE_ORDER.indexOf(current);
  if (index === -1) return [];
  return [...GENERIC_STAGE_ORDER.slice(index + 1), "rejected"];
}

interface JobWithCount extends Job {
  applicant_count: number;
}

function CandidateCard({
  candidate,
  onOpen,
  onDragStart,
  dragging,
  showJob,
}: {
  candidate: Candidate;
  onOpen: () => void;
  onDragStart: () => void;
  dragging: boolean;
  showJob: boolean;
}) {
  const latestInvite = candidate.interview_invites?.[candidate.interview_invites.length - 1];
  const pendingOffer = candidate.offer?.status === "pending";
  const acceptedOffer = candidate.offer?.status === "accepted";
  const pendingInvite = latestInvite?.status === "pending";
  const confirmedInvite = latestInvite?.status === "confirmed";
  const awaitingOnboarding =
    candidate.status === "onboarding" && !candidate.onboarding.confirmed;
  const readyOnboarding =
    candidate.status === "onboarding" && candidate.onboarding.confirmed;
  const hired = candidate.status === "hired";
  const abandoned = candidate.status === "abandoned";

  return (
    <div
      draggable={DRAGGABLE_STATUSES.has(candidate.status)}
      onDragStart={(event) => {
        if (!DRAGGABLE_STATUSES.has(candidate.status)) return;
        event.dataTransfer.setData("text/plain", String(candidate.application_id));
        event.dataTransfer.effectAllowed = "move";
        onDragStart();
      }}
      onClick={onOpen}
      className={cn(
        "cursor-grab rounded-lg border border-line bg-surface p-3 transition-colors hover:border-primary active:cursor-grabbing",
        dragging && "drag-ghost",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{candidate.candidate_name}</p>
          <p className="mt-0.5 text-[11px] text-muted">
            {candidate.structured.title} · {candidate.structured.years_of_experience} 年
          </p>
          {showJob && (
            <p className="mt-0.5 truncate text-[10px] text-primary">{candidate.job_title}</p>
          )}
        </div>
        <span
          className={cn(
            "shrink-0 px-1.5 py-0.5 text-xs font-semibold tabular-nums",
            candidate.match_score >= 80
              ? "bg-success-soft text-success"
              : candidate.match_score >= 60
                ? "bg-primary-soft text-ink"
                : "bg-warning-soft text-warning",
          )}
        >
          {Math.round(candidate.match_score)}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        {(candidate.structured.skills || []).slice(0, 3).map((skill) => (
          <span key={skill} className="rounded-md bg-neutral-soft px-1.5 py-0.5 text-[10px] text-muted">
            {skill}
          </span>
        ))}
      </div>
      {(pendingOffer ||
        acceptedOffer ||
        pendingInvite ||
        confirmedInvite ||
        awaitingOnboarding ||
        readyOnboarding ||
        hired ||
        abandoned) && (
        <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px] font-medium">
          {pendingOffer && <span className="text-warning">Offer 待确认</span>}
          {acceptedOffer && <span className="text-success">Offer 已接受</span>}
          {pendingInvite && <span className="text-warning">面试待确认</span>}
          {confirmedInvite && <span className="text-primary">面试已确认</span>}
          {awaitingOnboarding && <span className="text-warning">待确认入职</span>}
          {readyOnboarding && <span className="text-primary">待入职</span>}
          {hired && <span className="text-success">已入职</span>}
          {abandoned && <span className="text-muted">放弃入职</span>}
        </div>
      )}
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
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [noteDraft, setNoteDraft] = useState("");

  const jobsQuery = useQuery({
    queryKey: ["my-jobs"],
    queryFn: () => api.get<{ items: JobWithCount[] }>("/jobs/mine"),
  });

  const jobParam = searchParams.get("jobId");
  const allJobs = jobParam === "all";
  const jobId = allJobs ? 0 : Number(jobParam || jobsQuery.data?.items[0]?.id || 0);
  const candidateScope: number | "all" = allJobs ? "all" : jobId;

  useEffect(() => {
    if (!jobParam && jobsQuery.data?.items[0]) {
      setSearchParams({ jobId: String(jobsQuery.data.items[0].id) }, { replace: true });
    }
  }, [jobsQuery.data, jobParam, setSearchParams]);

  const candidatesQuery = useQuery({
    queryKey: ["candidates", candidateScope],
    queryFn: () =>
      api.get<{ items: Candidate[] }>(
        `/match/candidates${jobId ? `?job_id=${jobId}` : ""}`,
      ),
    enabled: allJobs || Boolean(jobId),
    refetchInterval: 30_000,
  });

  const currentJob = useMemo(
    () => jobsQuery.data?.items.find((job) => job.id === jobId),
    [jobsQuery.data, jobId],
  );

  const draggingCandidate = useMemo(
    () =>
      draggingId
        ? candidatesQuery.data?.items.find(
            (item) => item.application_id === draggingId,
          ) || null
        : null,
    [candidatesQuery.data, draggingId],
  );

  const canDropInto = (status: string) =>
    Boolean(
      draggingCandidate && statusTargets(draggingCandidate.status).includes(status),
    );

  // 面试邀约 / Offer 变更后，用最新候选人数据刷新详情弹窗
  useEffect(() => {
    if (!selected) return;
    const fresh = candidatesQuery.data?.items.find(
      (item) => item.application_id === selected.application_id,
    );
    if (fresh && fresh !== selected) setSelected(fresh);
  }, [candidatesQuery.data, selected]);

  const patchMutation = useMutation({
    mutationFn: ({
      applicationId,
      status,
      note,
    }: {
      applicationId: number;
      status: string;
      note?: string;
    }) => api.patch(`/applications/${applicationId}/status`, { status, note }),
    onMutate: async ({ applicationId, status, note }) => {
      setActionError("");
      await queryClient.cancelQueries({ queryKey: ["candidates", candidateScope] });
      const previous = queryClient.getQueryData<{ items: Candidate[] }>(["candidates", candidateScope]);
      queryClient.setQueryData<{ items: Candidate[] }>(["candidates", candidateScope], (old) =>
        old
          ? {
              items: old.items.map((item) =>
                item.application_id === applicationId
                  ? { ...item, status, ...(note ? { status_note: note } : {}) }
                  : item,
              ),
            }
          : old,
      );
      return { previous };
    },
    onError: (err, vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["candidates", candidateScope], context.previous);
        const restored = context.previous.items.find(
          (item) => item.application_id === vars.applicationId,
        );
        if (restored) setSelected(restored);
      }
      setActionError(err instanceof ApiError ? err.message : "状态更新失败，请重试");
    },
    onSuccess: () => setActionError(""),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates", candidateScope] });
      queryClient.invalidateQueries({ queryKey: ["my-jobs"] });
    },
  });

  const downloadCandidateResume = async () => {
    if (!selected || !selected.has_resume_file) return;
    setDownloadBusy(true);
    setDownloadError("");
    try {
      const blob = await fetchBlob(`/applications/${selected.application_id}/resume-file`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = selected.resume_file_name || "resume";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "原简历下载失败");
    } finally {
      setDownloadBusy(false);
    }
  };

  const handleDrop = (status: string, event: React.DragEvent) => {
    event.preventDefault();
    setDropTarget(null);
    setDraggingId(null);
    const applicationId = Number(event.dataTransfer.getData("text/plain"));
    if (!applicationId) return;
    const candidate = candidatesQuery.data?.items.find((item) => item.application_id === applicationId);
    if (!candidate || candidate.status === status) return;
    if (!statusTargets(candidate.status).includes(status)) return;
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

  const jobs = jobsQuery.data?.items || [];
  const totalApplicants = jobs.reduce((sum, job) => sum + job.applicant_count, 0);

  return (
    <div className="flex h-full flex-col px-6 py-4">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3 animate-fade-up">
        <h1 className="text-base font-semibold">候选人看板</h1>
        <Select
          className="w-[280px]"
          ariaLabel="选择岗位"
          value={allJobs ? "all" : String(jobId || "")}
          onChange={(value) => setSearchParams({ jobId: value })}
          options={[
            { label: `全部岗位（${totalApplicants} 份投递）`, value: "all" },
            ...jobs.map((job) => ({
              label: `${job.title}（${job.applicant_count} 份投递）`,
              value: String(job.id),
            })),
          ]}
        />
      </header>

      {actionError && (
        <p className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
          {actionError}
        </p>
      )}

      {(currentJob || allJobs) && (
        <div className="mt-3 flex flex-wrap items-center gap-3 px-1 text-xs text-muted animate-fade-in">
          <span className="font-medium text-ink">
            {allJobs ? "全部岗位" : currentJob?.title}
          </span>
          {allJobs ? (
            <span>共 {jobs.length} 个岗位</span>
          ) : (
            currentJob && (
              <span>
                {currentJob.location} · {currentJob.experience_min}-{currentJob.experience_max} 年 ·{" "}
                {currentJob.salary_min}-{currentJob.salary_max}K
              </span>
            )
          )}
          <span className="ml-auto tabular-nums">
            共 {candidatesQuery.data?.items.length || 0} 位候选人
          </span>
        </div>
      )}

      {jobsQuery.isLoading || candidatesQuery.isLoading ? (
        <div className="mt-5 flex flex-1 gap-3 overflow-x-auto pb-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-64 w-[200px] shrink-0" />
          ))}
        </div>
      ) : !jobsQuery.data?.items.length ? (
        <div className="mt-6">
          <EmptyState title="还没有岗位" description="先去岗位管理发布一个岗位，再回来看候选人。" />
        </div>
      ) : (
        <div className="mt-5 flex flex-1 gap-3 overflow-x-auto pb-4">
          {COLUMNS.map((column) => (
            <section
              key={column.key}
              onDragOver={(event) => {
                if (!canDropInto(column.key)) return;
                event.preventDefault();
                setDropTarget(column.key);
              }}
              onDragLeave={() => setDropTarget((prev) => (prev === column.key ? null : prev))}
              onDrop={(event) => {
                if (!DROP_TARGET_STATUSES.has(column.key)) return;
                handleDrop(column.key, event);
              }}
              className={cn(
                "flex min-h-[240px] w-[200px] shrink-0 flex-col rounded-xl border border-line bg-surface p-2.5 transition-colors",
                dropTarget === column.key && "drop-active",
              )}
            >
              <div className="mb-2 flex items-center gap-2 px-1">
                <span className={cn("h-1.5 w-1.5 rounded-full", column.accent)} />
                <p className="text-xs font-semibold text-ink">{column.label}</p>
                <span className="ml-auto text-[10px] tabular-nums text-muted">{grouped[column.key]?.length || 0}</span>
              </div>
              <div className="space-y-2">
                {(grouped[column.key] || []).map((candidate) => (
                  <CandidateCard
                    key={candidate.application_id}
                    candidate={candidate}
                    showJob={allJobs}
                    dragging={draggingId === candidate.application_id}
                    onDragStart={() => setDraggingId(candidate.application_id)}
                    onOpen={() => {
                      setDownloadError("");
                      setNoteDraft(candidate.status_note || "");
                      setSelected(candidate);
                    }}
                  />
                ))}
                {!(grouped[column.key] || []).length && (
                  <div className="rounded-lg border border-dashed border-line py-8 text-center text-[10px] text-muted">
                    {DROP_TARGET_STATUSES.has(column.key) ? "拖到这里" : "暂无候选人"}
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
        onClose={() => {
          setSelected(null);
          setDownloadError("");
          setNoteDraft("");
        }}
        footer={
          selected ? (
            <div className="flex w-full flex-wrap items-center justify-between gap-2">
              {DRAGGABLE_STATUSES.has(selected.status) ? (
                <Select
                  className="w-[160px]"
                  ariaLabel="候选人状态"
                  value={selected.status}
                  onChange={(status) => {
                    if (status === selected.status) return;
                    patchMutation.mutate({
                      applicationId: selected.application_id,
                      status,
                    });
                    setSelected({ ...selected, status });
                  }}
                  options={[selected.status, ...statusTargets(selected.status)].map(
                    (key) => ({
                      label: STATUS_META[key]?.label || key,
                      value: key,
                    }),
                  )}
                />
              ) : (
                <Badge tone={STATUS_META[selected.status]?.tone || "default"}>
                  {selected.status_label}
                </Badge>
              )}
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

            <div className="border-t border-line pt-4">
              <p className="text-xs font-semibold text-ink">招聘备注</p>
              <p className="mt-0.5 text-[11px] text-muted">会展示在求职者的「我的投递」进度中。</p>
              <div className="mt-2">
                <Textarea
                  value={noteDraft}
                  onChange={(event) => setNoteDraft(event.target.value)}
                  placeholder="如：一面技术基础扎实，二面重点考察项目深度"
                />
              </div>
              <div className="mt-2 flex justify-end">
                <Button
                  size="sm"
                  variant="soft"
                  loading={patchMutation.isPending}
                  disabled={noteDraft.trim() === (selected.status_note || "")}
                  onClick={() =>
                    patchMutation.mutate({
                      applicationId: selected.application_id,
                      status: selected.status,
                      note: noteDraft.trim(),
                    })
                  }
                >
                  保存备注
                </Button>
              </div>
            </div>

            {selected.has_resume_file && (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-ink">原始简历</p>
                  <p className="mt-0.5 truncate text-[11px] text-muted">
                    {selected.resume_file_name || "候选人已上传简历文件"}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="soft"
                  loading={downloadBusy}
                  onClick={() => void downloadCandidateResume()}
                >
                  <DownloadIcon className="h-3.5 w-3.5" /> 下载原简历
                </Button>
              </div>
            )}
            {downloadError && (
              <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
                {downloadError}
              </p>
            )}

            {selected.cover_letter && (
              <div className="border-t border-line pt-4">
                <p className="text-xs font-semibold text-ink">求职信</p>
                <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-muted">
                  {selected.cover_letter}
                </p>
              </div>
            )}

            <EmployerPipeline candidate={selected} jobId={allJobs ? "all" : jobId} />

            <div className="border-t border-line pt-4">
              <p className="text-xs font-semibold text-ink">规则分明细</p>
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
                      <span className="text-ink">{label}</span>
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
            </div>

            {selected.match_explanation ? (
              <div className="border-l-2 border-primary bg-neutral-soft p-4">
                <p className="text-xs font-semibold text-ink">AI 评估</p>
                <p className="mt-1 text-xs leading-relaxed text-muted">
                  {selected.match_explanation.summary}
                </p>
                {selected.match_explanation.gaps.length > 0 && (
                  <p className="mt-2 text-xs leading-relaxed text-muted">
                    差距：{selected.match_explanation.gaps.join("；")}
                  </p>
                )}
              </div>
            ) : (
              <div className="border-l-2 border-line bg-neutral-soft p-4 text-xs leading-relaxed text-muted">
                还没有 AI 深度评估。可以在「AI 招聘助手」里说：「详细评一下这位候选人」，助手会生成完整评估。
              </div>
            )}

            {selected.structured.work_experience?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-ink">工作经历</p>
                <div className="mt-2 space-y-2">
                  {selected.structured.work_experience.map((work, index) => (
                    <div key={index} className="border-l-2 border-line pl-3">
                      <div className="flex justify-between text-xs">
                        <span className="font-medium">{work.company}</span>
                        <span className="text-muted">{work.period}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted">{work.role}</p>
                      <ul className="mt-1 space-y-0.5">
                        {work.highlights.map((item) => (
                          <li key={item} className="text-[11px] leading-relaxed text-muted">
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
        jobId={duelCandidate?.job_id || jobId}
        jobTitle={duelCandidate?.job_title || currentJob?.title || ""}
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
