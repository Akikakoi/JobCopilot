import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Job } from "../lib/types";
import { ArrowRightIcon, BookmarkIcon } from "../components/icons";
import { Badge, Button, EmptyState, Skeleton, cn } from "../components/ui";

type SavedJob = Job & { my_feedback: "save" };

export function SavedJobsPage() {
  const queryClient = useQueryClient();

  const savedQuery = useQuery({
    queryKey: ["saved-jobs"],
    queryFn: () => api.get<{ items: SavedJob[]; total: number }>("/jobs/mine/saved"),
  });

  const removeMutation = useMutation({
    mutationFn: (jobId: number) => api.post(`/jobs/${jobId}/feedback`, { action: "clear" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["match-jobs"] });
      queryClient.invalidateQueries({ queryKey: ["job-feedback"] });
    },
  });

  const jobs = savedQuery.data?.items || [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <header className="animate-fade-up">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[26px] font-semibold tracking-tight">我的收藏</h1>
            <p className="mt-1 text-xs text-muted">
              收藏的岗位会保留在这里，已关闭的岗位也可以查看详情。
            </p>
          </div>
          <Link to="/seeker/jobs">
            <Button variant="ghost" size="sm">
              继续找岗位
            </Button>
          </Link>
        </div>
      </header>

      {savedQuery.isLoading && (
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-[168px] w-full" />
          ))}
        </div>
      )}

      {savedQuery.data && jobs.length === 0 && (
        <div className="mt-8">
          <EmptyState
            title="还没有收藏岗位"
            description="在岗位列表或详情页点击「收藏」，心仪的岗位就会出现在这里。"
            action={
              <Link to="/seeker/jobs">
                <Button>去找岗位</Button>
              </Link>
            }
          />
        </div>
      )}

      {jobs.length > 0 && (
        <div className="mt-6 grid gap-3 md:grid-cols-2 stagger">
          {jobs.map((job) => (
            <a
              key={job.id}
              href={`/seeker/jobs/${job.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="group block rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-primary"
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
                  <Badge tone={job.status === "open" ? "success" : "default"}>
                    {job.status === "open" ? "在招" : "已关闭"}
                  </Badge>
                  <button
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      removeMutation.mutate(job.id);
                    }}
                    className={cn(
                      "flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium text-success transition-colors hover:bg-success-soft",
                    )}
                  >
                    <BookmarkIcon className="h-3.5 w-3.5" filled />
                    取消收藏
                  </button>
                </div>
                <span className="flex items-center gap-1 text-[11px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                  查看详情 <ArrowRightIcon className="h-3.5 w-3.5" />
                </span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
