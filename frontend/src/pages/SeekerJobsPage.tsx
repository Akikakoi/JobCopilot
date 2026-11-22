import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { CITY_DISTRICTS, JOB_CATEGORIES, JOB_TYPES } from "../lib/jobMeta";
import { CityPicker } from "../components/CityPicker";
import type { Job, MatchItem, Resume } from "../lib/types";
import { ArrowRightIcon, BookmarkIcon, SearchIcon } from "../components/icons";
import { Badge, Button, EmptyState, Input, Select, Skeleton, cn } from "../components/ui";

function ScorePill({ score }: { score: number }) {
  const tone = score >= 80 ? "text-success" : score >= 60 ? "text-primary" : "text-warning";
  return (
    <span className="inline-flex items-baseline gap-1 text-xs">
      <span className={cn("font-semibold tabular-nums", tone)}>{Math.round(score)}</span>
      <span className="text-muted">匹配</span>
    </span>
  );
}

const PAGE_SIZE = 12;

export function SeekerJobsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"match" | "all">("match");
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState({ keywords: "", location: "", district: "", salary_min: "", category: "", job_type: "" });
  const [filters, setFilters] = useState({ keywords: "", location: "", district: "", salary_min: "", category: "", job_type: "" });
  const listRef = useRef<HTMLDivElement>(null);

  const districtOptions = CITY_DISTRICTS[draft.location] || [];

  // 筛选条件变化后自动查询（关键词会触发语义检索，做 500ms 防抖），无需再点搜索
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => {
      setFilters(draft);
      setPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [draft]);

  const resumeQuery = useQuery({
    queryKey: ["resume", "mine"],
    queryFn: () => api.get<Resume | null>("/resumes/mine"),
  });

  const matchQuery = useQuery({
    queryKey: ["match-jobs", 50],
    queryFn: () => api.get<{ items: MatchItem[] }>("/match/jobs-for-me?top_n=50&limit=50"),
    enabled: tab === "match" && Boolean(resumeQuery.data?.has_embedding),
    staleTime: 30_000,
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.keywords) params.set("keywords", filters.keywords);
      if (filters.location) params.set("location", filters.location);
      if (filters.district) params.set("district", filters.district);
      if (filters.salary_min) params.set("salary_min", filters.salary_min);
      if (filters.category) params.set("category", filters.category);
      if (filters.job_type) params.set("job_type", filters.job_type);
      return api.get<{ items: Job[]; total: number }>(`/jobs?${params.toString()}`);
    },
    enabled: tab === "all",
  });

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    setFilters(draft);
    setPage(1);
  };

  // 智能匹配结果同样受筛选条件约束，避免「切到智能匹配后城市条件失效」
  const matchJobs = (matchQuery.data?.items || []).filter((job) => {
    const kw = filters.keywords.trim().toLowerCase();
    if (kw) {
      const haystack = [
        job.title,
        job.company_name,
        ...(job.required_skills || []),
        ...(job.preferred_skills || []),
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(kw)) return false;
    }
    if (filters.location) {
      const loc = filters.location.trim();
      if (!job.location.includes(loc) && !["不限", "远程"].includes(job.location)) return false;
    }
    if (filters.district && job.district !== filters.district) return false;
    if (filters.salary_min && job.salary_max < Number(filters.salary_min)) return false;
    if (filters.category && job.category !== filters.category) return false;
    if (filters.job_type && job.job_type !== filters.job_type) return false;
    return true;
  });

  const totalJobs = jobsQuery.data?.total || 0;
  const pageCount = Math.max(1, Math.ceil(totalJobs / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pagedJobs = (jobsQuery.data?.items || []).slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );

  const gotoPage = (next: number) => {
    setPage(next);
    listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
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
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h1 className="text-[26px] font-semibold tracking-tight">找岗位</h1>
          <Link to="/seeker/resume">
            <Button variant="ghost" size="sm">
              更新简历
            </Button>
          </Link>
        </div>
      </header>

      <form onSubmit={submitSearch} className="mt-6 flex flex-wrap gap-2 animate-fade-up">
        <div className="relative min-w-[220px] flex-1">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder="搜索岗位、技能或公司，如 Python"
            value={draft.keywords}
            onChange={(event) => setDraft({ ...draft, keywords: event.target.value })}
          />
        </div>
        <CityPicker
          className="w-[132px]"
          ariaLabel="城市"
          value={draft.location}
          onChange={(location) => setDraft({ ...draft, location, district: "" })}
        />
        {districtOptions.length > 0 && (
          <Select
            className="w-[124px]"
            ariaLabel="区县"
            value={draft.district}
            onChange={(district) => setDraft({ ...draft, district })}
            options={[
              { label: "全部区县", value: "" },
              ...districtOptions.map((district) => ({ label: district, value: district })),
            ]}
          />
        )}
        <Select
          className="w-[140px]"
          ariaLabel="薪资"
          value={draft.salary_min}
          onChange={(salary_min) => setDraft({ ...draft, salary_min })}
          options={[
            { label: "不限薪资", value: "" },
            ...[15, 20, 25, 30, 40].map((value) => ({
              label: `${value}K 以上`,
              value: String(value),
            })),
          ]}
        />
        <Select
          className="w-[132px]"
          ariaLabel="岗位类别"
          value={draft.category}
          onChange={(category) => setDraft({ ...draft, category })}
          options={[
            { label: "全部类别", value: "" },
            ...JOB_CATEGORIES.map((category) => ({ label: category, value: category })),
          ]}
        />
        <Select
          className="w-[120px]"
          ariaLabel="工作性质"
          value={draft.job_type}
          onChange={(job_type) => setDraft({ ...draft, job_type })}
          options={[
            { label: "全部性质", value: "" },
            ...JOB_TYPES.map((type) => ({ label: type, value: type })),
          ]}
        />
      </form>

      <div className="mt-5 flex items-center gap-1 rounded-xl border border-line bg-surface p-1 animate-fade-up md:w-fit">
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
              "rounded-lg px-4 py-1.5 text-xs font-medium transition-colors",
              tab === value ? "bg-primary-soft text-primary" : "text-muted hover:text-ink",
            )}
          >
            {label}
          </button>
        ))}
        {tab === "match" && matchQuery.data && (
          <span className="ml-2 pr-2 text-[11px] text-muted">
            已按匹配分排序 · {matchJobs.length} 个推荐
          </span>
        )}
        {tab === "all" && totalJobs > 0 && (
          <span className="ml-2 pr-2 text-[11px] text-muted">共 {totalJobs} 个岗位</span>
        )}
      </div>

      <div className="mt-5" ref={listRef}>
        {tab === "match" && !resumeQuery.isLoading && !resumeQuery.data?.has_embedding && (
          <EmptyState
            title="先添加一份简历，才能开启智能匹配"
            description="上传 PDF / DOCX 或粘贴简历文本，AI 会抽取结构化信息并计算岗位匹配度。"
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
              <div className="rounded-2xl border border-danger bg-danger-soft px-4 py-3 text-sm text-danger">
                {(matchQuery.error as Error).message}
              </div>
            )}
            {matchQuery.data && matchQuery.data.items.length === 0 && (
              <EmptyState title="暂无在招岗位" description="岗位库为空，请先让招聘方发布岗位。" />
            )}
            {matchQuery.data && matchQuery.data.items.length > 0 && matchJobs.length === 0 && (
              <EmptyState
                title="没有符合筛选条件的匹配岗位"
                description="换个城市或放宽薪资 / 类别条件，也可以切到「全部岗位」看看。"
              />
            )}
            <div className="grid gap-3 md:grid-cols-2 stagger">
              {matchJobs.map((job) => (
                <a
                  key={job.id}
                  href={`/seeker/jobs/${job.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group block cursor-pointer rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-primary"
                >
                  <div className="flex items-start justify-between gap-3">
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
                          event.preventDefault();
                          event.stopPropagation();
                          toggleFeedback(job, "save");
                        }}
                        className={cn(
                          "flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] transition-colors",
                          job.my_feedback === "save"
                            ? "bg-success-soft font-medium text-success"
                            : "text-muted hover:text-ink",
                        )}
                        title="收藏岗位"
                      >
                        <BookmarkIcon
                          className="h-3.5 w-3.5"
                          filled={job.my_feedback === "save"}
                        />
                        {job.my_feedback === "save" ? "已收藏" : "收藏"}
                      </button>
                      <button
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          toggleFeedback(job, "dislike");
                        }}
                        className={cn(
                          "rounded-lg px-2 py-1 text-[11px] transition-colors",
                          job.my_feedback === "dislike"
                            ? "bg-danger-soft font-medium text-danger"
                            : "text-muted hover:text-ink",
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
                </a>
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
              {pagedJobs.map((job) => (
                <a
                  key={job.id}
                  href={`/seeker/jobs/${job.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group block cursor-pointer rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-primary"
                >
                  <div className="flex items-start justify-between gap-3">
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
                </a>
              ))}
            </div>

            {totalJobs > PAGE_SIZE && (
              <div className="mt-6 flex items-center justify-center gap-3">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={currentPage === 1}
                  onClick={() => gotoPage(currentPage - 1)}
                >
                  上一页
                </Button>
                <span className="text-xs tabular-nums text-muted">
                  第 {currentPage} / {pageCount} 页
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={currentPage === pageCount}
                  onClick={() => gotoPage(currentPage + 1)}
                >
                  下一页
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
