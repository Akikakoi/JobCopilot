import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { CompanyDetail } from "../lib/types";
import { ArrowLeftIcon, ArrowRightIcon, BuildingIcon } from "../components/icons";
import { Badge, Button, Card, EmptyState, Skeleton } from "../components/ui";

export function CompanyPage() {
  const { id } = useParams<{ id: string }>();
  const companyId = Number(id);

  const companyQuery = useQuery({
    queryKey: ["company", companyId],
    queryFn: () => api.get<CompanyDetail>(`/companies/${companyId}`),
    enabled: Number.isFinite(companyId) && companyId > 0,
  });

  const company = companyQuery.data;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <Link
        to="/seeker/jobs"
        className="mb-4 inline-flex items-center gap-1.5 text-xs font-medium text-muted transition-colors hover:text-ink"
      >
        <ArrowLeftIcon className="h-3.5 w-3.5" /> 返回岗位列表
      </Link>

      {companyQuery.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {companyQuery.isError && (
        <EmptyState
          title="公司信息加载失败"
          description="公司可能不存在，或网络暂时异常。"
          action={
            <Link to="/seeker/jobs">
              <Button>返回岗位列表</Button>
            </Link>
          }
        />
      )}

      {company && (
        <>
          <Card className="p-6 animate-fade-up">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-line bg-neutral-soft">
                <BuildingIcon className="h-6 w-6 text-muted" />
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-xl font-semibold tracking-tight">{company.name}</h1>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {company.industry && <span className="chip">{company.industry}</span>}
                  <Badge tone="success">在招 {company.open_job_count} 个岗位</Badge>
                </div>
              </div>
            </div>
            <div className="mt-5 border-t border-line pt-4">
              <p className="text-[11px] font-semibold text-muted">公司简介</p>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-ink">
                {company.description || "该公司还没有填写简介。"}
              </p>
            </div>
          </Card>

          <section className="mt-6">
            <div className="flex items-baseline justify-between">
              <h2 className="text-[15px] font-semibold">在招岗位</h2>
              <span className="text-xs tabular-nums text-muted">{company.jobs.length} 个</span>
            </div>

            {company.jobs.length === 0 ? (
              <div className="mt-4">
                <EmptyState title="暂无在招岗位" description="可以先收藏公司，之后再来看看。" />
              </div>
            ) : (
              <div className="mt-3 grid gap-3 md:grid-cols-2 stagger">
                {company.jobs.map((job) => (
                  <a
                    key={job.id}
                    href={`/seeker/jobs/${job.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group block rounded-2xl border border-line bg-surface p-5 transition-colors hover:border-primary"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="min-w-0 flex-1 truncate text-[15px] font-semibold group-hover:text-primary">
                        {job.title}
                      </h3>
                      <span className="shrink-0 text-sm font-semibold text-primary">
                        {job.salary_min}-{job.salary_max}K
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted">
                      {job.location} · {job.experience_min}-{job.experience_max} 年
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {job.required_skills.slice(0, 5).map((skill) => (
                        <span key={skill} className="chip">
                          {skill}
                        </span>
                      ))}
                    </div>
                    <div className="mt-4 flex items-center justify-end border-t border-line pt-3">
                      <span className="flex items-center gap-1 text-[11px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                        查看详情 <ArrowRightIcon className="h-3.5 w-3.5" />
                      </span>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
