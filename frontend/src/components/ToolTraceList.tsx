import { useState } from "react";
import type { ToolTrace } from "../lib/types";
import { CheckIcon, ChevronIcon } from "./icons";
import { cn } from "./ui";

const TOOL_LABELS: Record<string, string> = {
  get_my_resume: "读取简历",
  search_jobs: "检索岗位",
  get_job_detail: "查看岗位详情",
  match_jobs_for_me: "运行匹配管线",
  suggest_resume_improvements: "分析简历差距",
  apply_to_job: "投递岗位",
  get_my_applications: "查询投递记录",
  start_mock_interview: "准备模拟面试",
  save_memory: "写入长期记忆",
  search_memory: "检索长期记忆",
  generate_job_description: "生成 JD 草稿",
  create_job: "发布岗位",
  update_job: "更新岗位",
  list_my_jobs: "查询在招岗位",
  list_candidates: "查询候选人",
  screen_candidate: "深度评估候选人",
  rank_candidates: "候选人排序",
  update_application_status: "推进候选人状态",
  list_my_pipeline: "查询投递进展",
  respond_interview_invite: "响应面试邀约",
  respond_offer: "响应 Offer",
  create_interview_invite: "发送面试邀约",
  cancel_interview_invite: "取消面试邀约",
  complete_interview_invite: "标记面试完成",
  create_offer: "发送 Offer",
};

export function ToolTraceList({ traces }: { traces: ToolTrace[] }) {
  const [open, setOpen] = useState(false);
  if (traces.length === 0) return null;
  const running = traces.some((trace) => trace.status === "running");

  return (
    <div className="mt-2 rounded-lg border border-line bg-neutral-soft">
      <button
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[11px] text-muted"
      >
        <span
          className={cn(
            "flex h-4 w-4 items-center justify-center rounded-full",
            running ? "animate-spin border border-line border-t-primary" : "bg-success-soft text-success",
          )}
        >
          {!running && <CheckIcon className="h-2.5 w-2.5" />}
        </span>
        <span className="flex-1">{running ? "正在调用工具…" : `已调用 ${traces.length} 个工具`}</span>
        <span className="text-[10px] text-muted">
          {traces.map((t) => TOOL_LABELS[t.name] || t.name).join(" · ")}
        </span>
        <ChevronIcon className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-2 border-t border-line px-3 py-2">
          {traces.map((trace) => (
            <div key={trace.id} className="border-l-2 border-line pl-2">
              <p className="text-[11px] font-medium text-ink">
                {TOOL_LABELS[trace.name] || trace.name}
                <span className="ml-1.5 font-normal text-muted">{trace.name}</span>
              </p>
              <p className="mt-1 break-all text-[10px] text-muted">
                参数：{JSON.stringify(trace.args)}
              </p>
              {trace.result && (
                <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-all rounded bg-surface p-1.5 text-[10px] leading-relaxed text-muted">
                  {trace.result}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
