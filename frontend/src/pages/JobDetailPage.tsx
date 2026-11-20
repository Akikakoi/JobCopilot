import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { Job, MatchDetail } from "../lib/types";
import { ArrowLeftIcon, ArrowRightIcon, BookmarkIcon } from "../components/icons";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Modal,
  ProgressBar,
  ScoreRing,
  Skeleton,
  Textarea,
  cn,
} from "../components/ui";

function BreakdownRow({
  label,
  score,
  max,
  hint,
}: {
  label: string;
  score: number;
  max: number;
  hint?: string;
}) {
  const tone = score / max >= 0.8 ? "success" : score / max >= 0.4 ? "primary" : "warning";
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-ink">{label}</span>
        <span className="tabular-nums text-muted">
          {score} / {max}
        </span>
      </div>
      <div className="mt-1.5">
        <ProgressBar value={score} max={max} tone={tone} />
      </div>
      {hint && <p className="mt-1 text-[11px] text-muted">{hint}</p>}
    </div>
  );
}

function MatchPanel({ detail, loading, error }: { detail?: MatchDetail; loading: boolean; error: unknown }) {
  if (loading) {
    return (
      <Card className="p-5">
        <Skeleton className="mx-auto h-[132px] w-[132px] rounded-full" />
        <Skeleton className="mt-6 h-4 w-full" />
        <Skeleton className="mt-3 h-4 w-5/6" />
        <Skeleton className="mt-3 h-4 w-2/3" />
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-5">
        <p className="text-sm font-semibold">暂时无法计算匹配度</p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted">
          {(error as Error).message}。上传简历后即可查看逐项得分与 AI 解读。
        </p>
        <Link to="/seeker/resume" className="mt-4 block">
          <Button size="sm" className="w-full">
            去添加简历
          </Button>
        </Link>
      </Card>
    );
  }

  if (!detail) return null;
  const { explanation, breakdown } = detail;

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-col items-center">
          <ScoreRing score={detail.match_score} />
          <p className="mt-3 text-center text-xs leading-relaxed text-muted">{explanation.summary}</p>
        </div>

        <div className="mt-5 space-y-3.5">
          <BreakdownRow
            label="必需技能"
            score={breakdown.skills_required.score}
            max={40}
            hint={
              breakdown.skills_required.missing?.length
                ? `已命中：${breakdown.skills_required.matched.join("、") || "无"}；缺失：${breakdown.skills_required.missing.join("、")}`
                : "全部命中"
            }
          />
          <BreakdownRow
            label="加分技能"
            score={breakdown.skills_preferred.score}
            max={10}
            hint={breakdown.skills_preferred.matched.length ? `命中：${breakdown.skills_preferred.matched.join("、")}` : "暂无命中"}
          />
          <BreakdownRow
            label="工作年限"
            score={breakdown.experience.score}
            max={20}
            hint={`你 ${breakdown.experience.resume_years} 年 · 要求 ${breakdown.experience.required_years} 年`}
          />
          <BreakdownRow
            label="地点匹配"
            score={breakdown.location.score}
            max={15}
            hint={`你的期望：${breakdown.location.resume_locations.join("、") || "未填写"} · 岗位：${breakdown.location.job_location}`}
          />
          <BreakdownRow
            label="薪资匹配"
            score={breakdown.salary.score}
            max={15}
            hint={`你的期望：${breakdown.salary.resume_range.filter(Boolean).join("-") || "未填写"}K · 岗位：${breakdown.salary.job_range.join("-")}K`}
          />
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold">AI 匹配解读</h3>

        {explanation.reasons.length > 0 && (
          <div className="mt-3">
            <p className="text-[11px] font-semibold text-success">匹配理由</p>
            <ul className="mt-1.5 space-y-1.5">
              {explanation.reasons.map((item) => (
                <li key={item} className="flex gap-2 text-xs leading-relaxed text-muted">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-success" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {explanation.gaps.length > 0 && (
          <div className="mt-4">
            <p className="text-[11px] font-semibold text-warning">主要差距</p>
            <ul className="mt-1.5 space-y-1.5">
              {explanation.gaps.map((item) => (
                <li key={item} className="flex gap-2 text-xs leading-relaxed text-muted">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-warning" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}

        {explanation.suggestions.length > 0 && (
          <div className="mt-4 border-l-2 border-primary bg-neutral-soft p-3">
            <p className="text-[11px] font-semibold text-primary">补齐建议</p>
            <ul className="mt-1.5 space-y-1.5">
              {explanation.suggestions.map((item) => (
                <li key={item} className="flex gap-2 text-xs leading-relaxed text-muted">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [applyOpen, setApplyOpen] = useState(false);
  const [coverLetter, setCoverLetter] = useState("");
  const [applyError, setApplyError] = useState("");
  const [applied, setApplied] = useState(false);

  const jobQuery = useQuery({
    queryKey: ["job", id],
    queryFn: () => api.get<Job>(`/jobs/${id}`),
    enabled: Boolean(id),
  });

  const matchQuery = useQuery({
    queryKey: ["match-detail", id],
    queryFn: () => api.get<MatchDetail>(`/match/job/${id}`),
    enabled: Boolean(id),
    retry: false,
  });

  const feedbackQuery = useQuery({
    queryKey: ["job-feedback", id],
    queryFn: () => api.get<{ action: "save" | "dislike" | null }>(`/jobs/${id}/feedback`),
    enabled: Boolean(id),
  });

  const feedbackMutation = useMutation({
    mutationFn: (action: "save" | "dislike" | "clear") =>
      api.post(`/jobs/${id}/feedback`, { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job-feedback", id] });
      queryClient.invalidateQueries({ queryKey: ["match-jobs"] });
    },
  });

  const feedbackAction = feedbackQuery.data?.action ?? null;
  const toggleFeedback = (action: "save" | "dislike") => {
    feedbackMutation.mutate(feedbackAction === action ? "clear" : action);
  };

  const applyMutation = useMutation({
    mutationFn: () =>
      api.post<{ id: number }>("/applications", {
        job_id: Number(id),
        cover_letter: coverLetter,
      }),
    onSuccess: () => {
      setApplied(true);
      setApplyOpen(false);
      queryClient.invalidateQueries({ queryKey: ["match-detail", id] });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["match-jobs"] });
    },
    onError: (error) => {
      setApplyError(error instanceof ApiError ? error.message : "投递失败，请重试");
    },
  });

  const job = jobQuery.data;
  const isApplied = applied || Boolean(matchQuery.data?.applied);

  if (jobQuery.isLoading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="mt-4 h-40 w-full" />
      </div>
    );
  }

  if (!job) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 md:px-8">
        <EmptyState
          title="岗位不存在"
          action={
            <Link to="/seeker/jobs">
              <Button>返回岗位列表</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <Link
        to="/seeker/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-muted transition-colors hover:text-ink"
      >
        <ArrowLeftIcon className="h-3.5 w-3.5" /> 返回岗位列表
      </Link>

      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card className="p-6 animate-fade-up">
            <div className="flex items-start gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h1 className="text-xl font-semibold tracking-tight">{job.title}</h1>
                  <span className="text-lg font-semibold text-primary">
                    {job.salary_min}-{job.salary_max}K
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted">
                  {job.company_name} · {job.company_industry} · {job.location}
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Badge tone={job.status === "open" ? "success" : "default"}>
                    {job.status === "open" ? "在招" : "已关闭"}
                  </Badge>
                  <span className="chip">{job.experience_min}-{job.experience_max} 年经验</span>
                  <span className="chip">月薪 {job.salary_min}-{job.salary_max}K</span>
                </div>
              </div>
            </div>

            <div className="mt-6 space-y-4">
              <div>
                <p className="text-[11px] font-semibold text-muted">必需技能</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {job.required_skills.map((skill) => (
                    <span key={skill} className="chip chip-primary">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-muted">加分技能</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {job.preferred_skills.length ? (
                    job.preferred_skills.map((skill) => (
                      <span key={skill} className="chip">
                        {skill}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-muted">无</span>
                  )}
                </div>
              </div>
              <div>
                <p className="text-[11px] font-semibold text-muted">岗位描述</p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-ink">
                  {job.description}
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
              <p className="text-xs text-muted">
                {isApplied ? "你已投递该岗位，可在「我的投递」查看进度" : "投递后招聘方会看到你的匹配分与解读"}
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleFeedback("save")}
                  className={cn(
                    "flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[11px] transition-colors",
                    feedbackAction === "save"
                      ? "bg-success-soft font-medium text-success"
                      : "text-muted hover:text-ink",
                  )}
                >
                  <BookmarkIcon className="h-3.5 w-3.5" filled={feedbackAction === "save"} />
                  {feedbackAction === "save" ? "已收藏" : "收藏"}
                </button>
                <button
                  onClick={() => toggleFeedback("dislike")}
                  className={cn(
                    "rounded-lg px-2.5 py-1.5 text-[11px] transition-colors",
                    feedbackAction === "dislike"
                      ? "bg-danger-soft font-medium text-danger"
                      : "text-muted hover:text-ink",
                  )}
                >
                  {feedbackAction === "dislike" ? "已标记不感兴趣" : "不感兴趣"}
                </button>
                <Button
                  onClick={() => {
                    setApplyError("");
                    setApplyOpen(true);
                  }}
                  disabled={isApplied || job.status !== "open"}
                  className={cn(isApplied && "bg-success hover:bg-success")}
                >
                  {isApplied ? "已投递" : "投递简历"}
                  {!isApplied && <ArrowRightIcon className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          </Card>
        </div>

        <div className="lg:sticky lg:top-6 lg:self-start">
          <MatchPanel
            detail={matchQuery.data}
            loading={matchQuery.isLoading}
            error={matchQuery.error}
          />
        </div>
      </div>

      <Modal
        open={applyOpen}
        title={`投递「${job.title}」`}
        onClose={() => setApplyOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setApplyOpen(false)}>
              取消
            </Button>
            <Button loading={applyMutation.isPending} onClick={() => applyMutation.mutate()}>
              确认投递
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-xs leading-relaxed text-muted">
            你的简历与匹配解读会一并发送给招聘方。可附上一段简短的求职信（选填）。
          </p>
          <Textarea
            value={coverLetter}
            onChange={(event) => setCoverLetter(event.target.value)}
            placeholder="例如：你好，我有 3 年 Python 后端经验，主导过订单系统的性能优化……"
            className="min-h-[140px]"
          />
          {applyError && (
            <p className="rounded-xl border border-danger bg-danger-soft px-3.5 py-2.5 text-xs text-danger">{applyError}</p>
          )}
        </div>
      </Modal>
    </div>
  );
}
