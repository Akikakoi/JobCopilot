import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Job, MatchItem, Resume } from "../lib/types";
import { ArrowRightIcon, SearchIcon } from "../components/icons";
import { Badge, Button, EmptyState, Input, Skeleton, cn } from "../components/ui";

function CompanyAvatar({ name }: { name: string }) {
  return (
    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 text-sm font-semibold text-slate-500">
      {name.slice(0, 1)}
    </div>
  );
}

function ScorePill({ score }: { score: number }) {
  const tone = score >= 80 ? "success" : score >= 60 ? "primary" : "warning";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums",
        tone === "success" && "bg-[#EAF8F0] text-success",
        tone === "primary" && "bg-[#EEF3FF] text-primary",
        tone === "warning" && "bg-[#FDF3E7] text-warning",
      )}
    >
      {Math.round(score)} 分匹配
    </span>
  );
}

export function SeekerJobsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"match" | "all">("match");
  const [draft, setDraft] = useState({ keywords: "", location: "", salary_min: "" });
  const [filters, setFilters] = useState({ keywords: "", location: "", salary_min: "" });

  const resumeQuery = useQuery({
    queryKey: ["resume", "mine"],
    queryFn: () => api.get<Resume | null>("/resumes/mine"),
  });

  const matchQuery = useQuery({
    queryKey: ["match-jobs", 20],
    queryFn: () => api.get<{ items: MatchItem[] }>("/match/jobs-for-me?limit=20"),
    enabled: tab === "match" && Boolean(resumeQuery.data?.has_embedding),
    staleTime: 30_000,
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.keywords) params.set("keywords", filters.keywords);
      if (filters.location) params.set("location", filters.location);
      if (filters.salary_min) params.set("salary_min", filters.salary_min);
      return api.get<{ items: Job[]; total: number }>(`/jobs?${params.toString()}`);
    },
    enabled: tab === "all",
  });

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setTab("all");
  };

  const feedbackMutation = useMutation({
    mutationFn: ({ jobId, action }: { jobId: number; action: "save" | "dislike" | "clear" }) =>
      api.post(`/jobs/${jobId}/feedback`, { action }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["match-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job-feedback"] });
    },
  });

  const toggleFeedback = (job: MatchItem, action: "save" | "dislike") => {
    feedbackMutation.mutate({
      jobId: job.id,
      action: job.my_feedback === action ? "clear" : action,
    });
  };

  const loading =
    (tab === "match" && matchQuery.isLoading) || (tab === "all" && jobsQuery.isLoading);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <header className="animate-fade-up">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
          Job Matching
        </p>
        <div className="mt-1.5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight">发现适合你的机会</h1>
            <p className="mt-1 text-sm text-muted">
              三段式匹配管线：向量召回 → 规则精排 → AI 解读，分数透明可解释。
            </p>
          </div>
          <Link to="/seeker/resume">
            <Button variant="ghost" size="sm">
              更新简历
            </Button>
          </Link>
        </div>
      </header>

      <form onSubmit={submitSearch} className="mt-6 flex flex-wrap gap-2 animate-fade-up">
        <div className="relative min-w-[220px] flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            className="pl-9"
            placeholder="搜索岗位、技能或公司，如 Python"
            value={draft.keywords}
            onChange={(event) => setDraft({ ...draft, keywords: event.target.value })}
          />
        </div>
        <select
          className="input w-[132px]"
          value={draft.location}
          onChange={(event) => setDraft({ ...draft, location: event.target.value })}
        >
          <option value="">全部城市</option>
          {["上海", "北京", "深圳", "杭州", "广州", "成都", "远程"].map((city) => (
            <option key={city} value={city}>
              {city}
            </option>
          ))}
        </select>
        <select
          className="input w-[140px]"
          value={draft.salary_min}
          onChange={(event) => setDraft({ ...draft, salary_min: event.target.value })}
        >
          <option value="">不限薪资</option>
          {[15, 20, 25, 30, 40].map((value) => (
            <option key={value} value={value}>
              {value}K 以上
            </option>
          ))}
        </select>
        <Button type="submit" variant="soft">
          搜索
        </Button>
      </form>

      <div className="mt-5 flex items-center gap-1 rounded-xl border border-line bg-white p-1 animate-fade-up md:w-fit">
        {(
          [
            ["match", "智能匹配"],
            ["all", "全部岗位"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            onClick={() => setTab(value)}
            className={cn(
              "rounded-lg px-4 py-1.5 text-xs font-medium transition-all duration-200",
              tab === value ? "bg-[#EEF3FF] text-primary" : "text-muted hover:text-ink",
            )}
            style={{ transitionTimingFunction: "var(--ease-out)" }}
          >
            {label}
          </button>
        ))}
        {tab === "match" && matchQuery.data && (
          <span className="ml-2 pr-2 text-[11px] text-muted">
            已按匹配分排序 · {matchQuery.data.items.length} 个推荐
          </span>
        )}
      </div>

      <div className="mt-5">
        {tab === "match" && !resumeQuery.isLoading && !resumeQuery.data?.has_embedding && (
          <EmptyState
            title="先添加一份简历，才能开启智能匹配"
            description="上传 PDF / DOCX 或粘贴简历文本，AI 会抽取结构化信息并生成向量，然后为你计算岗位匹配度。"
            action={
              <Link to="/seeker/resume">
                <Button>去添加简历</Button>
              </Link>
            }
          />
        )}

        {loading && (
          <div className="grid gap-3 md:grid-cols-2">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="card p-5">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="mt-3 h-4 w-1/2" />
                <Skeleton className="mt-4 h-8 w-full" />
              </div>
            ))}
          </div>
        )}

        {tab === "match" && resumeQuery.data?.has_embedding && (
          <>
            {matchQuery.isError && (
              <div className="rounded-2xl bg-[#FDECEC] px-4 py-3 text-sm text-danger">
                {(matchQuery.error as Error).message}
              </div>
            )}
            {matchQuery.data && matchQuery.data.items.length === 0 && (
              <EmptyState title="暂无在招岗位" description="岗位库为空，请先让招聘方发布岗位。" />
            )}
            <div className="grid gap-3 md:grid-cols-2 stagger">
              {matchQuery.data?.items.map((job) => (
                <article
                  key={job.id}
                  onClick={() => navigate(`/seeker/jobs/${job.id}`)}
                  className="group cursor-pointer rounded-2xl border border-line bg-white p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                  style={{ transitionTimingFunction: "var(--ease-out)" }}
                >
                  <div className="flex items-start gap-3">
                    <CompanyAvatar name={job.company_name} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="truncate text-[15px] font-semibold group-hover:text-primary">
                          {job.title}
                        </h3>
                        <span className="shrink-0 text-sm font-semibold text-primary">
                          {job.salary_min}-{job.salary_max}K
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted">
                        {job.company_name} · {job.location} · {job.experience_min}-{job.experience_max} 年
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {job.required_skills.slice(0, 5).map((skill) => (
                      <span key={skill} className="chip">
                        {skill}
                      </span>
                    ))}
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
                    <div className="flex items-center gap-2">
                      <ScorePill score={job.match_score} />
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleFeedback(job, "save");
                        }}
                        className={cn(
                          "rounded-lg px-2 py-1 text-[11px] transition-colors",
                          job.my_feedback === "save"
                            ? "bg-[#EAF8F0] font-medium text-success"
                            : "text-slate-400 hover:bg-slate-100 hover:text-slate-600",
                        )}
                        title="收藏岗位"
                      >
                        {job.my_feedback === "save" ? "★ 已收藏" : "☆ 收藏"}
                      </button>
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleFeedback(job, "dislike");
                        }}
                        className={cn(
                          "rounded-lg px-2 py-1 text-[11px] transition-colors",
                          job.my_feedback === "dislike"
                            ? "bg-[#FDECEC] font-medium text-danger"
                            : "text-slate-400 hover:bg-slate-100 hover:text-slate-600",
                        )}
                        title="不感兴趣"
                      >
                        {job.my_feedback === "dislike" ? "已隐藏偏好" : "不感兴趣"}
                      </button>
                    </div>
                    <span className="flex items-center gap-1 text-[11px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                      查看解读 <ArrowRightIcon className="h-3.5 w-3.5" />
                    </span>
                  </div>

                  {job.breakdown.skills_required.missing &&
                    job.breakdown.skills_required.missing.length > 0 && (
                      <p className="mt-2 text-[11px] text-warning">
                        还差：{job.breakdown.skills_required.missing.slice(0, 3).join("、")}
                      </p>
                    )}
                </article>
              ))}
            </div>
          </>
        )}

        {tab === "all" && (
          <>
            {jobsQuery.data && jobsQuery.data.items.length === 0 && (
              <EmptyState title="没有找到匹配的岗位" description="换个关键词或放宽筛选条件试试。" />
            )}
            <div className="grid gap-3 md:grid-cols-2 stagger">
              {jobsQuery.data?.items.map((job) => (
                <article
                  key={job.id}
                  onClick={() => navigate(`/seeker/jobs/${job.id}`)}
                  className="group cursor-pointer rounded-2xl border border-line bg-white p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md"
                  style={{ transitionTimingFunction: "var(--ease-out)" }}
                >
                  <div className="flex items-start gap-3">
                    <CompanyAvatar name={job.company_name} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="truncate text-[15px] font-semibold group-hover:text-primary">
                          {job.title}
                        </h3>
                        <span className="shrink-0 text-sm font-semibold text-primary">
                          {job.salary_min}-{job.salary_max}K
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-xs text-muted">
                        {job.company_name} · {job.location} · {job.experience_min}-{job.experience_max} 年
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {job.required_skills.slice(0, 5).map((skill) => (
                      <span key={skill} className="chip">
                        {skill}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 flex items-center justify-between border-t border-line pt-3">
                    <Badge tone={job.status === "open" ? "success" : "default"}>
                      {job.status === "open" ? "在招" : "已关闭"}
                    </Badge>
                    <span className="flex items-center gap-1 text-[11px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                      查看详情 <ArrowRightIcon className="h-3.5 w-3.5" />
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="mt-10 rounded-2xl border border-dashed border-line bg-white/60 px-6 py-4 text-center text-xs text-muted">
        匹配分 = 必需技能 40 + 加分技能 10 + 年限 20 + 地点 15 + 薪资 15，满分 100
      </div>
    </div>
  );
}
