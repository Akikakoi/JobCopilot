import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, streamChat } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { AgentMessage, AgentSession, ChatEvent, ToolTrace } from "../lib/types";
import { PlusIcon, SendIcon, SparkIcon } from "../components/icons";
import { Button, Skeleton, cn } from "../components/ui";
import { Markdown } from "../components/Markdown";
import { ToolTraceList } from "../components/ToolTraceList";

interface UiMessage {
  key: string;
  role: "user" | "assistant";
  content: string;
  traces: ToolTrace[];
  streaming?: boolean;
}

const SUGGESTIONS: Record<string, string[]> = {
  seeker: [
    "帮我找适合我的岗位",
    "我的简历和好岗位还差什么？",
    "帮我模拟一次后端面试",
    "我想去上海，薪资 25K 以上",
  ],
  employer: [
    "帮我招一个 3 年经验的 Python 后端，预算 25-35K，上海",
    "看看我的岗位有哪些候选人",
    "帮我给排名第一的候选人做深度评估",
  ],
};

function toUiMessages(items: AgentMessage[]): UiMessage[] {
  const result: UiMessage[] = [];
  const toolResults = new Map<string, string>();
  items.forEach((item) => {
    if (item.role === "tool" && item.tool_call_id) {
      toolResults.set(item.tool_call_id, item.content);
    }
  });

  items.forEach((item) => {
    if (item.role === "user") {
      result.push({ key: `m-${item.id}`, role: "user", content: item.content, traces: [] });
    } else if (item.role === "assistant") {
      const traces: ToolTrace[] = (item.tool_calls || []).map((call) => ({
        id: call.id,
        name: call.function.name,
        args: (() => {
          try {
            return JSON.parse(call.function.arguments || "{}");
          } catch {
            return {};
          }
        })(),
        result: toolResults.get(call.id),
        status: "done",
      }));
      if (item.content || traces.length) {
        result.push({
          key: `m-${item.id}`,
          role: "assistant",
          content: item.content,
          traces,
        });
      }
    }
  });
  return result;
}

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map((index) => (
        <span
          key={index}
          className="h-1.5 w-1.5 rounded-full bg-slate-400"
          style={{
            animation: "blink 1.2s infinite",
            animationDelay: `${index * 160}ms`,
          }}
        />
      ))}
    </span>
  );
}

export function ChatPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const sendLockRef = useRef(false);
  const role = user?.role || "seeker";

  const sessionsQuery = useQuery({
    queryKey: ["agent-sessions"],
    queryFn: () => api.get<{ items: AgentSession[] }>("/agent/sessions"),
  });

  const messagesQuery = useQuery({
    queryKey: ["agent-messages", sessionId],
    queryFn: () => api.get<{ items: AgentMessage[] }>(`/agent/sessions/${sessionId}/messages`),
    enabled: Boolean(sessionId),
  });

  useEffect(() => {
    if (!sessionId && sessionsQuery.data?.items.length) {
      setSessionId(sessionsQuery.data.items[0].id);
    }
  }, [sessionId, sessionsQuery.data]);

  const history = messagesQuery.data;
  const appliedSessionRef = useRef<number | null>(null);
  useEffect(() => {
    // 只在切到某个会话后应用一次历史，避免流式过程中被旧数据覆盖
    if (history && sessionId && appliedSessionRef.current !== sessionId && !streaming) {
      appliedSessionRef.current = sessionId;
      setMessages(toUiMessages(history.items));
    }
  }, [history, sessionId, streaming]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const sessions = sessionsQuery.data?.items || [];
  const currentSession = useMemo(
    () => sessions.find((session) => session.id === sessionId),
    [sessions, sessionId],
  );

  const createSession = async (): Promise<number> => {
    const session = await api.post<AgentSession>("/agent/sessions", {});
    appliedSessionRef.current = session.id;
    setSessionId(session.id);
    setMessages([]);
    queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
    return session.id;
  };

  const startNewSession = () => {
    // 新建会话时中止仍在进行的流，避免两条流同时写入不同会话
    abortRef.current?.abort();
    abortRef.current = null;
    sendLockRef.current = false;
    setStreaming(false);
    void createSession();
  };

  const send = async (raw?: string) => {
    const content = (raw ?? input).trim();
    if (!content || sendLockRef.current) return;
    sendLockRef.current = true;
    setError("");
    setInput("");

    let activeSession = sessionId;
    try {
      if (!activeSession) activeSession = await createSession();
    } catch (err) {
      sendLockRef.current = false;
      setError(err instanceof ApiError ? err.message : "创建会话失败");
      setInput(content);
      return;
    }

    const userKey = `local-${Date.now()}`;
    const assistantKey = `${userKey}-a`;
    setMessages((prev) => [
      ...prev,
      { key: userKey, role: "user", content, traces: [] },
      { key: assistantKey, role: "assistant", content: "", traces: [], streaming: true },
    ]);
    setStreaming(true);

    const patchAssistant = (patch: (message: UiMessage) => UiMessage) => {
      setMessages((prev) =>
        prev.map((message) => (message.key === assistantKey ? patch(message) : message)),
      );
    };

    const controller = new AbortController();
    abortRef.current = controller;

    const onEvent = (event: ChatEvent) => {
      if (event.type === "token") {
        patchAssistant((message) => ({ ...message, content: message.content + (event.content || "") }));
      } else if (event.type === "tool_start" && event.id) {
        patchAssistant((message) => ({
          ...message,
          traces: [
            ...message.traces,
            {
              id: event.id as string,
              name: event.name || "",
              args: event.args || {},
              status: "running",
            },
          ],
        }));
      } else if (event.type === "tool_end" && event.id) {
        patchAssistant((message) => ({
          ...message,
          traces: message.traces.map((trace) =>
            trace.id === event.id
              ? { ...trace, status: "done", result: event.result || trace.result }
              : trace,
          ),
        }));
      } else if (event.type === "done") {
        patchAssistant((message) => ({ ...message, streaming: false }));
        queryClient.invalidateQueries({ queryKey: ["agent-sessions"] });
        queryClient.invalidateQueries({ queryKey: ["agent-messages", activeSession] });
      } else if (event.type === "error") {
        patchAssistant((message) => ({
          ...message,
          streaming: false,
          content: message.content || `⚠️ ${event.message || "对话失败"}`,
        }));
      }
    };

    try {
      await streamChat(activeSession, content, onEvent, controller.signal);
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError(err instanceof ApiError ? err.message : "对话中断，请重试");
      }
      patchAssistant((message) => ({ ...message, streaming: false }));
    } finally {
      patchAssistant((message) => ({ ...message, streaming: false }));
      sendLockRef.current = false;
      setStreaming(false);
      abortRef.current = null;
    }
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  };

  return (
    <div className="flex h-full min-h-[520px]">
      <aside className="hidden w-[248px] shrink-0 flex-col border-r border-line bg-white/70 lg:flex">
        <div className="flex items-center justify-between px-4 py-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">会话</p>
          <button
            onClick={() => startNewSession()}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#EEF3FF] text-primary transition-colors hover:bg-[#E2EAFF]"
            title="新会话"
          >
            <PlusIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-4">
          {sessionsQuery.isLoading &&
            Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          {sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => {
                if (streaming) return;
                setMessages([]);
                setSessionId(session.id);
                setError("");
              }}
              className={cn(
                "w-full truncate rounded-xl px-3 py-2.5 text-left text-xs transition-colors duration-200",
                session.id === sessionId
                  ? "bg-[#EEF3FF] font-medium text-primary"
                  : "text-slate-600 hover:bg-slate-50",
              )}
            >
              {session.title}
            </button>
          ))}
          {!sessionsQuery.isLoading && sessions.length === 0 && (
            <p className="px-3 py-6 text-center text-[11px] leading-relaxed text-muted">
              还没有会话
              <br />
              直接开始对话即可创建
            </p>
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-line bg-white/70 px-4 py-3 backdrop-blur md:px-6">
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold">
              {role === "employer" ? "AI 招聘助手" : "AI 求职助手"}
            </h1>
            <p className="truncate text-[11px] text-muted">
              {currentSession?.title || "新会话"} · 工具调用过程对用户透明可查
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => startNewSession()} className="lg:hidden">
              <PlusIcon className="h-3.5 w-3.5" /> 新会话
            </Button>
            <span className="hidden items-center gap-1.5 rounded-full bg-[#EAF8F0] px-2.5 py-1 text-[10px] font-medium text-success md:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-success" /> Agent 在线
            </span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-5">
            {messages.length === 0 && (
              <div className="animate-fade-up py-8 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent text-white shadow-md">
                  <SparkIcon className="h-6 w-6" />
                </div>
                <h2 className="mt-4 text-lg font-semibold tracking-tight">
                  {role === "employer" ? "让招聘助手帮你找人" : "让求职助手帮你找活"}
                </h2>
                <p className="mx-auto mt-1.5 max-w-md text-xs leading-relaxed text-muted">
                  {role === "employer"
                    ? "发布岗位、排序候选人、推进流程，都可以直接说。"
                    : "描述你的偏好，助手会调用匹配管线给出真实岗位与解读。"}
                </p>
                <div className="mx-auto mt-5 flex max-w-xl flex-wrap justify-center gap-2">
                  {SUGGESTIONS[role].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => void send(suggestion)}
                      className="rounded-full border border-line bg-white px-3.5 py-1.5 text-xs text-slate-600 transition-all hover:border-primary/40 hover:text-primary"
                      style={{ transitionTimingFunction: "var(--ease-out)" }}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) =>
              message.role === "user" ? (
                <div key={message.key} className="flex justify-end animate-fade-up">
                  <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
                    {message.content}
                  </div>
                </div>
              ) : (
                <div key={message.key} className="flex gap-3 animate-fade-up">
                  <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-[10px] font-bold text-white">
                    AI
                  </div>
                  <div className="min-w-0 flex-1">
                    <div
                      className={cn(
                        "rounded-2xl rounded-tl-md border border-line bg-white px-4 py-3",
                        message.streaming && !message.content && "thinking",
                      )}
                    >
                      {message.content ? (
                        <div>
                          <Markdown text={message.content} />
                          {message.streaming && <span className="caret" />}
                        </div>
                      ) : message.streaming ? (
                        <TypingDots />
                      ) : (
                        <p className="text-xs text-muted">（本轮无文字回复）</p>
                      )}
                      <ToolTraceList traces={message.traces} />
                    </div>
                  </div>
                </div>
              ),
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="border-t border-line bg-white/80 px-4 py-3 backdrop-blur md:px-8">
          <div className="mx-auto max-w-3xl">
            {error && (
              <p className="mb-2 rounded-lg bg-[#FDECEC] px-3 py-2 text-[11px] text-danger">{error}</p>
            )}
            <div className="flex items-end gap-2 rounded-2xl border border-line bg-white p-2 shadow-sm focus-within:border-primary/40 focus-within:shadow-[0_0_0_4px_rgba(42,91,255,0.08)]">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onKeyDown}
                rows={1}
                placeholder={
                  role === "employer"
                    ? "描述招聘需求，或询问候选人情况…（Enter 发送，Shift+Enter 换行）"
                    : "说说你想找什么样的工作…（Enter 发送，Shift+Enter 换行）"
                }
                className="max-h-40 min-h-[38px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-slate-400"
              />
              <Button
                size="sm"
                disabled={!input.trim() || streaming}
                onClick={() => void send()}
                className="mb-0.5 h-9 w-9 rounded-xl p-0"
                title="发送"
              >
                <SendIcon className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-1.5 text-center text-[10px] text-slate-400">
              Agent 可能会调用工具，执行结果会以折叠面板展示
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
