import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Application } from "../lib/types";
import { formatDateTime } from "../lib/format";
import { ArrowRightIcon } from "../components/icons";
import { Badge, Button, Card, EmptyState, Skeleton, STATUS_META, cn } from "../components/ui";
import { SeekerPipeline } from "../components/PipelinePanel";

const FLOW = ["submitted", "screening", "interview", "offer", "onboarding"];

function Stepper({ status }: { status: string }) {
  if (status === "rejected" || status === "abandoned") {
    return (
      <div className="flex items-center gap-2 text-xs text-danger">
        <span className="h-2 w-2 rounded-full bg-danger" />
        流程终止 · {status === "abandoned" ? "放弃入职" : "未通过"}
      </div>
    );
  }
  const activeIndex = Math.max(
    0,
    status === "hired" ? FLOW.length - 1 : FLOW.indexOf(status),
  );
  return (
    <div className="flex items-center">
      {FLOW.map((step, index) => {
        const done = index <= activeIndex;
        const meta = STATUS_META[step];
        return (
          <div key={step} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-semibold transition-colors duration-300",
                  done ? "border-primary bg-primary text-white" : "border-line bg-surface text-muted",
                )}
              >
                {index + 1}
              </span>
              <span className={cn("whitespace-nowrap text-[10px]", done ? "text-primary" : "text-muted")}>
                {meta.label}
              </span>
            </div>
            {index < FLOW.length - 1 && (
              <div className="mx-2 mb-4 h-px flex-1 bg-line">
                <div
                  className="h-px bg-primary transition-[width] duration-500"
                  style={{ width: index < activeIndex ? "100%" : "0%" }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function ApplicationsPage() {
  const appsQuery = useQuery({
    queryKey: ["applications", "mine"],
    queryFn: () => api.get<{ items: Application[] }>("/applications/mine"),
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <header className="animate-fade-up">
        <h1 className="text-[26px] font-semibold tracking-tight">我的投递</h1>
      </header>

      {appsQuery.isLoading && (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-32 w-full" />
          ))}
        </div>
      )}

      {appsQuery.data && appsQuery.data.items.length === 0 && (
        <div className="mt-8">
          <EmptyState
            title="还没有投递记录"
            description="去岗位列表挑一个心仪的岗位，或者直接让 AI 求职助手帮你找。"
            action={
              <Link to="/seeker/jobs">
                <Button>去找岗位</Button>
              </Link>
            }
          />
        </div>
      )}

      <div className="mt-6 space-y-3 stagger">
        {appsQuery.data?.items.map((app) => {
          const meta =
            app.status === "offer" && app.offer
              ? app.offer.status === "accepted"
                ? { label: "Offer 已接受", tone: "success" as const }
                : app.offer.status === "expired"
                  ? { label: "Offer 已过期", tone: "danger" as const }
                  : { label: "Offer 阶段", tone: "warning" as const }
              : STATUS_META[app.status] || STATUS_META.submitted;
          const latestEventNote = app.events[app.events.length - 1]?.note || "";
          const showStatusNote = Boolean(app.status_note) && app.status_note !== latestEventNote;
          return (
            <Card key={app.id} className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-[15px] font-semibold">{app.job_title}</h3>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {app.company_name} · 投递于 {formatDateTime(app.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {app.match_score != null && (
                    <div className="text-right">
                      <p className="text-lg font-semibold tabular-nums text-primary">
                        {Math.round(app.match_score)}
                      </p>
                      <p className="text-[10px] text-muted">匹配分</p>
                    </div>
                  )}
                  <a
                    href={`/seeker/jobs/${app.job_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink transition-colors hover:border-muted hover:bg-neutral-soft"
                  >
                    详情 <ArrowRightIcon className="h-3.5 w-3.5" />
                  </a>
                </div>
              </div>

              <div className="mt-5">
                <Stepper status={app.status} />
                {app.status === "hired" && (
                  <p className="mt-2 text-xs text-success">
                    已完成入职{app.onboarding.date ? ` · ${app.onboarding.date}` : ""}
                  </p>
                )}
              </div>

              {app.events.length > 0 && (
                <div className="mt-3 rounded-lg bg-neutral-soft px-3 py-2.5">
                  <p className="text-[11px] font-semibold text-muted">状态记录</p>
                  <ul className="mt-1.5 space-y-1.5">
                    {[...app.events].reverse().map((event) => (
                      <li
                        key={event.id}
                        className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-[11px]"
                      >
                        <span className="tabular-nums text-muted">
                          {formatDateTime(event.created_at)}
                        </span>
                        <span className="text-ink">
                          {event.from_status_label} → {event.to_status_label}
                        </span>
                        {event.note && <span className="text-muted">备注：{event.note}</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {showStatusNote && (
                <p className="mt-3 rounded-lg bg-neutral-soft px-3 py-2 text-xs text-muted">
                  招聘方备注：{app.status_note}
                </p>
              )}

              <SeekerPipeline app={app} />

              {app.match_explanation?.summary && (
                <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
                  AI 解读：{app.match_explanation.summary}
                </p>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
