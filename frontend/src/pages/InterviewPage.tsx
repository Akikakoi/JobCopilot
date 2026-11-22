import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { Interview, InterviewSummary, Job } from "../lib/types";
import { ArrowRightIcon, MicIcon } from "../components/icons";
import { JobPicker } from "../components/JobPicker";
import { InterviewReportView } from "../components/InterviewReportView";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  Skeleton,
  Textarea,
  cn,
} from "../components/ui";

const CATEGORY_LABELS: Record<string, string> = {
  technical: "技术题",
  project: "项目题",
  behavior: "行为题",
};

export function InterviewPage() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");

  const listQuery = useQuery({
    queryKey: ["interviews", "mine"],
    queryFn: () => api.get<{ items: InterviewSummary[] }>("/interviews/mine"),
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs", "interview-picker"],
    queryFn: () => api.get<{ items: Job[] }>("/jobs"),
  });

  const activeQuery = useQuery({
    queryKey: ["interview", activeId],
    queryFn: () => api.get<Interview>(`/interviews/${activeId}`),
    enabled: activeId !== null,
  });

  const createMutation = useMutation({
    mutationFn: (jobId: number) => api.post<Interview>("/interviews", { job_id: jobId }),
    onSuccess: (data) => {
      queryClient.setQueryData(["interview", data.id], data);
      setActiveId(data.id);
      setAnswer("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["interviews", "mine"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "生成面试失败"),
  });

  const answerMutation = useMutation({
    mutationFn: ({ questionId, text }: { questionId: string; text: string }) =>
      api.post<Interview>(`/interviews/${activeId}/answers`, {
        question_id: questionId,
        answer: text,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["interview", data.id], data);
      setAnswer("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["interviews", "mine"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "提交回答失败"),
  });

  const completeMutation = useMutation({
    mutationFn: () => api.post<Interview>(`/interviews/${activeId}/complete`),
    onSuccess: (data) => {
      queryClient.setQueryData(["interview", data.id], data);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["interviews", "mine"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "生成报告失败"),
  });

  const interview = activeQuery.data;
  const questions = interview?.plan?.questions ?? [];
  const answeredIds = useMemo(
    () => new Set((interview?.answers ?? []).map((item) => item.question_id)),
    [interview],
  );
  const answeredCount = questions.filter((question) => answeredIds.has(question.id)).length;
  const currentQuestion = questions.find((question) => !answeredIds.has(question.id));

  useEffect(() => {
    setAnswer("");
  }, [activeId]);

  const startInterview = () => {
    if (!selectedJob) {
      setError("请先选择目标岗位");
      return;
    }
    setError("");
    createMutation.mutate(Number(selectedJob));
  };

  const submitAnswer = () => {
    if (!currentQuestion || answer.trim().length < 5) return;
    answerMutation.mutate({ questionId: currentQuestion.id, text: answer.trim() });
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <header className="animate-fade-up">
        <h1 className="text-[26px] font-semibold tracking-tight">面试训练</h1>
      </header>

      <div className="mt-6 grid gap-5 lg:grid-cols-[320px_1fr]">
        <div className="space-y-4">
          <Card className="p-5">
            <p className="text-[11px] font-semibold text-muted">开始新面试</p>
            <JobPicker
              className="mt-3"
              ariaLabel="目标岗位"
              value={selectedJob}
              onChange={setSelectedJob}
              jobs={jobsQuery.data?.items || []}
              placeholder="选择目标岗位"
            />
            <Button
              className="mt-3 w-full"
              loading={createMutation.isPending}
              onClick={startInterview}
            >
              <MicIcon className="h-4 w-4" /> 生成面试题
            </Button>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              出题基于岗位必需技能与简历经历，约需 5-10 秒。
            </p>
          </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between px-1">
              <p className="text-[11px] font-semibold text-muted">历史记录</p>
              <span className="text-[10px] tabular-nums text-muted">{listQuery.data?.items.length || 0}</span>
            </div>
            <div className="mt-2 space-y-1.5">
              {listQuery.isLoading &&
                Array.from({ length: 3 }).map((_, index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              {listQuery.data?.items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => {
                    setActiveId(item.id);
                    setError("");
                  }}
                  className={cn(
                    "w-full rounded-lg px-3 py-2.5 text-left transition-colors",
                    item.id === activeId ? "bg-primary-soft" : "hover:bg-neutral-soft",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        "truncate text-xs font-medium",
                        item.id === activeId ? "text-primary" : "text-ink",
                      )}
                    >
                      {item.job_title}
                    </span>
                    {item.status === "completed" ? (
                      <Badge tone="success">{Math.round(item.overall_score || 0)} 分</Badge>
                    ) : (
                      <Badge tone="primary">进行中</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-[10px] text-muted">
                    {item.company_name} · 已答 {item.answered_count}/{item.question_count}
                  </p>
                </button>
              ))}
              {!listQuery.isLoading && !listQuery.data?.items.length && (
                <p className="px-1 py-4 text-center text-[11px] text-muted">还没有面试记录</p>
              )}
            </div>
          </Card>
        </div>

        <div>
          {error && (
            <p className="mb-4 rounded-xl border border-danger bg-danger-soft px-4 py-3 text-xs text-danger">{error}</p>
          )}

          {!activeId && (
            <EmptyState
              title="选择岗位，开始一次模拟面试"
              description="系统会结合岗位要求与你的简历出 6 道题，逐题作答后生成可解释的面试报告。"
            />
          )}

          {activeId && activeQuery.isLoading && (
            <div className="space-y-4">
              <Skeleton className="h-40 w-full" />
              <Skeleton className="h-56 w-full" />
            </div>
          )}

          {interview && interview.status === "completed" && interview.report && (
            <div className="animate-fade-up">
              <InterviewReportView interview={interview} />
              <div className="mt-4 flex justify-end">
                <Button variant="ghost" size="sm" onClick={() => setActiveId(null)}>
                  返回列表
                </Button>
              </div>
            </div>
          )}

          {interview && interview.status !== "completed" && (
            <div className="space-y-4 animate-fade-up">
              <Card className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold">{interview.job_title}</p>
                    <p className="text-[11px] text-muted">{interview.company_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-medium tabular-nums text-primary">
                      {answeredCount} / {questions.length}
                    </p>
                    <p className="text-[10px] text-muted">已完成题目</p>
                  </div>
                </div>
                <div className="mt-3">
                  <ProgressBar value={answeredCount} max={questions.length || 1} />
                </div>
              </Card>

              {currentQuestion ? (
                <Card className="p-6">
                  <div className="flex items-center gap-2">
                    <Badge tone="primary">
                      {CATEGORY_LABELS[currentQuestion.category] || currentQuestion.category}
                    </Badge>
                    <span className="text-[11px] text-muted">第 {answeredCount + 1} 题</span>
                  </div>
                  <h2 className="mt-3 text-base font-semibold leading-relaxed">
                    {currentQuestion.question}
                  </h2>
                  {currentQuestion.focus && (
                    <p className="mt-1.5 text-[11px] text-muted">考察点：{currentQuestion.focus}</p>
                  )}
                  <Textarea
                    className="mt-4 min-h-[160px] text-sm leading-relaxed"
                    placeholder="分点写下你的回答，尽量包含具体项目、数据与你的贡献……"
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                  />
                  <div className="mt-3 flex items-center justify-between">
                    <p className="text-[11px] text-muted">建议 80-200 字，越具体评分越准</p>
                    <Button
                      loading={answerMutation.isPending}
                      disabled={answer.trim().length < 5}
                      onClick={submitAnswer}
                    >
                      提交并下一题 <ArrowRightIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </Card>
              ) : (
                <Card className="p-6 text-center">
                  <p className="text-sm font-semibold">6 道题已全部作答</p>
                  <p className="mt-1.5 text-xs text-muted">
                    生成报告需要 10-20 秒，将对每题评分并汇总为改进建议。
                  </p>
                  <Button
                    className="mt-4"
                    loading={completeMutation.isPending}
                    onClick={() => completeMutation.mutate()}
                  >
                    生成面试报告
                  </Button>
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
