import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, streamDuel } from "../lib/api";
import type { DuelEvent, DuelTurn } from "../lib/types";
import { Markdown } from "./Markdown";
import { ToolTraceList } from "./ToolTraceList";
import { Button, Modal, cn } from "./ui";

interface DuelModalProps {
  open: boolean;
  jobId: number;
  jobTitle: string;
  applicationId: number;
  candidateName: string;
  onClose: () => void;
}

const SPEAKER = {
  seeker: {
    label: "求职者 Agent",
    sub: "候选人代理",
    avatar: "求",
    avatarClass: "bg-primary text-white",
    bubble: "rounded-tl-md border-line bg-white",
    labelClass: "text-primary",
  },
  employer: {
    label: "招聘方 Agent",
    sub: "企业代理",
    avatar: "招",
    avatarClass: "bg-ink text-white",
    bubble: "rounded-tr-md border-slate-200 bg-[#F8FAFC]",
    labelClass: "text-ink",
  },
} as const;

export function DuelModal({
  open,
  jobId,
  jobTitle,
  applicationId,
  candidateName,
  onClose,
}: DuelModalProps) {
  const [turns, setTurns] = useState<DuelTurn[]>([]);
  const [running, setRunning] = useState(false);
  const [finished, setFinished] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const seqRef = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  const start = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setTurns([]);
    setError("");
    setFinished(false);
    setRunning(true);
    seqRef.current = 0;

    const patchLast = (patch: (turn: DuelTurn) => DuelTurn) => {
      setTurns((prev) => {
        if (!prev.length) return prev;
        const next = [...prev];
        next[next.length - 1] = patch(next[next.length - 1]);
        return next;
      });
    };

    const onEvent = (event: DuelEvent) => {
      if (event.type === "speaker" && event.speaker) {
        seqRef.current += 1;
        setTurns((prev) => [
          ...prev,
          {
            key: `turn-${seqRef.current}`,
            speaker: event.speaker as "seeker" | "employer",
            round: event.round || 1,
            content: "",
            traces: [],
            streaming: true,
          },
        ]);
      } else if (event.type === "token") {
        patchLast((turn) => ({ ...turn, content: turn.content + (event.content || "") }));
      } else if (event.type === "tool_start" && event.id) {
        patchLast((turn) => ({
          ...turn,
          traces: [
            ...turn.traces,
            {
              id: event.id as string,
              name: event.name || "",
              args: event.args || {},
              status: "running",
            },
          ],
        }));
      } else if (event.type === "tool_end" && event.id) {
        patchLast((turn) => ({
          ...turn,
          traces: turn.traces.map((trace) =>
            trace.id === event.id
              ? { ...trace, status: "done", result: event.result || trace.result }
              : trace,
          ),
        }));
      } else if (event.type === "turn_end") {
        patchLast((turn) => ({
          ...turn,
          content: event.content || turn.content,
          streaming: false,
        }));
      } else if (event.type === "done") {
        setFinished(true);
        setRunning(false);
      } else if (event.type === "error") {
        setError(event.message || "对谈失败");
        patchLast((turn) => ({ ...turn, streaming: false }));
        setRunning(false);
      }
    };

    try {
      await streamDuel(jobId, applicationId, onEvent, controller.signal);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError(err instanceof ApiError ? err.message : "对谈中断，请重试");
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, [jobId, applicationId]);

  useEffect(() => {
    if (open) {
      void start();
    } else {
      abortRef.current?.abort();
    }
    return () => abortRef.current?.abort();
  }, [open, start]);

  const stop = () => {
    abortRef.current?.abort();
    setRunning(false);
    setTurns((prev) =>
      prev.map((turn) => (turn.streaming ? { ...turn, streaming: false } : turn)),
    );
  };

  return (
    <Modal
      open={open}
      title="AI 双方面谈（彩蛋）"
      width="max-w-3xl"
      onClose={onClose}
      footer={
        <div className="flex w-full items-center justify-between gap-2">
          <p className="text-[11px] text-muted">
            {running
              ? "双方 Agent 正在自主对谈…"
              : finished
                ? `对谈完成 · 共 ${turns.length} 轮发言`
                : turns.length
                  ? "对谈已停止"
                  : "准备中"}
          </p>
          <div className="flex gap-2">
            {running ? (
              <Button variant="ghost" size="sm" onClick={stop}>
                停止
              </Button>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => void start()}>
                重新开始
              </Button>
            )}
            <Button size="sm" onClick={onClose}>
              关闭
            </Button>
          </div>
        </div>
      }
    >
      <div className="mb-4 rounded-xl border border-line bg-[#F6F8FE] px-3.5 py-2.5 text-[11px] leading-relaxed text-slate-500">
        <span className="font-medium text-ink">{jobTitle}</span> · 候选人 {candidateName}。
        双方 Agent 会基于真实简历与岗位数据自主问答，工具调用对用户透明可见。
      </div>

      {error && (
        <p className="mb-3 rounded-xl bg-[#FDECEC] px-3 py-2 text-xs text-danger">{error}</p>
      )}

      <div className="space-y-4">
        {turns.map((turn) => {
          const meta = SPEAKER[turn.speaker];
          return (
            <div
              key={turn.key}
              className={cn("flex gap-2.5 animate-fade-up", turn.speaker === "employer" && "flex-row-reverse")}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-[11px] font-semibold",
                  meta.avatarClass,
                )}
              >
                {meta.avatar}
              </div>
              <div className={cn("min-w-0 max-w-[86%] flex-1")}>
                <div
                  className={cn(
                    "flex items-center gap-2",
                    turn.speaker === "employer" && "flex-row-reverse",
                  )}
                >
                  <span className={cn("text-[11px] font-semibold", meta.labelClass)}>{meta.label}</span>
                  <span className="text-[10px] text-slate-400">
                    {meta.sub} · 第 {turn.round} 轮
                  </span>
                </div>
                <div
                  className={cn(
                    "mt-1 rounded-2xl border px-3.5 py-2.5",
                    meta.bubble,
                    turn.streaming && !turn.content && "thinking",
                  )}
                >
                  {turn.content ? (
                    <div>
                      <Markdown text={turn.content} />
                      {turn.streaming && <span className="caret" />}
                    </div>
                  ) : turn.streaming ? (
                    <span className="text-xs text-slate-400">思考中…</span>
                  ) : (
                    <span className="text-xs text-muted">（本轮无内容）</span>
                  )}
                  <ToolTraceList traces={turn.traces} />
                </div>
              </div>
            </div>
          );
        })}

        {running && turns.length === 0 && (
          <div className="flex items-center gap-2 rounded-xl border border-dashed border-line px-4 py-6 text-xs text-muted thinking">
            双方 Agent 正在加载简历与岗位数据…
          </div>
        )}
        <div ref={endRef} />
      </div>
    </Modal>
  );
}
