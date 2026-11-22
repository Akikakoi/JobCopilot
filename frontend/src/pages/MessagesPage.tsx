import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ChatMessage, ConversationSummary } from "../lib/types";
import { formatShortDateTime } from "../lib/format";
import { Button, Card, EmptyState, Skeleton, Textarea, cn } from "../components/ui";

export function MessagesPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const listQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () =>
      api.get<{ items: ConversationSummary[]; unread: number }>("/conversations"),
    refetchInterval: 15_000,
  });

  const items = listQuery.data?.items || [];
  const selected = items.find((item) => item.id === selectedId) || null;

  useEffect(() => {
    if (!selectedId && items.length > 0) {
      setSelectedId(items[0].id);
      return;
    }
    if (selectedId && items.length > 0 && !items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  const messagesQuery = useQuery({
    queryKey: ["messages", selectedId],
    queryFn: () =>
      api.get<{ items: ChatMessage[] }>(
        `/conversations/${selectedId}/messages?limit=200`,
      ),
    enabled: Boolean(selectedId),
    refetchInterval: 5_000,
  });

  const messages = messagesQuery.data?.items || [];

  const readMutation = useMutation({
    mutationFn: (id: number) => api.post(`/conversations/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation-unread"] });
    },
  });

  // 打开有未读的会话时自动标记已读；用未读数量做条件避免反复触发
  useEffect(() => {
    if (selected && selected.unread > 0 && !readMutation.isPending) {
      readMutation.mutate(selected.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id, selected?.unread]);

  useEffect(() => {
    const node = scrollRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, selectedId]);

  const sendMutation = useMutation({
    mutationFn: () =>
      api.post(`/conversations/${selectedId}/messages`, { content: draft.trim() }),
    onSuccess: () => {
      setDraft("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["messages", selectedId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["conversation-unread"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "发送失败"),
  });

  const submit = () => {
    if (!selectedId || !draft.trim() || sendMutation.isPending) return;
    sendMutation.mutate();
  };

  const canSend = Boolean(selectedId && draft.trim());

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <header className="animate-fade-up">
        <h1 className="text-[26px] font-semibold tracking-tight">消息</h1>
        <p className="mt-1 text-xs text-muted">
          {user?.role === "employer"
            ? "与投递候选人的沟通记录，按投递建立会话。"
            : "与招聘方的沟通记录，按投递建立会话。"}
        </p>
      </header>

      {listQuery.isLoading && (
        <div className="mt-6 grid gap-4 md:grid-cols-[300px_1fr]">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      )}

      {!listQuery.isLoading && items.length === 0 && (
        <div className="mt-8">
          <EmptyState
            title="还没有消息"
            description={
              user?.role === "employer"
                ? "候选人投递岗位后，这里会出现对应会话。"
                : "投递岗位后，这里会出现与招聘方的会话。"
            }
          />
        </div>
      )}

      {items.length > 0 && (
        <div className="mt-6 grid gap-4 md:grid-cols-[300px_1fr]">
          <Card className="overflow-hidden p-0">
            <div className="max-h-[420px] overflow-y-auto md:max-h-[calc(100vh-170px)]">
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  className={cn(
                    "flex w-full flex-col gap-1 border-b border-line px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-neutral-soft",
                    item.id === selectedId && "bg-primary-soft",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[13px] font-medium text-ink">
                      {item.other_name}
                    </span>
                    {item.last_message && (
                      <span className="shrink-0 text-[10px] tabular-nums text-muted">
                        {formatShortDateTime(item.last_message.created_at)}
                      </span>
                    )}
                  </div>
                  <span className="truncate text-[11px] text-muted">{item.job_title}</span>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[11px] text-muted">
                      {item.last_message
                        ? `${item.last_message.mine ? "我：" : ""}${item.last_message.content}`
                        : "还没有消息，发一句问候吧"}
                    </span>
                    {item.unread > 0 && (
                      <span className="shrink-0 rounded-full bg-danger-soft px-1.5 py-0.5 text-[10px] font-medium text-danger">
                        {item.unread}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </Card>

          <Card className="flex min-h-[420px] flex-col overflow-hidden p-0">
            {selected ? (
              <>
                <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">{selected.other_name}</p>
                    <p className="mt-0.5 truncate text-[11px] text-muted">
                      {selected.job_title}
                      {selected.company_name && user?.role !== "employer"
                        ? ` · ${selected.company_name}`
                        : ""}
                    </p>
                  </div>
                </div>

                <div
                  ref={scrollRef}
                  className="flex-1 space-y-3 overflow-y-auto px-4 py-4 md:max-h-[calc(100vh-300px)]"
                >
                  {messagesQuery.isLoading && (
                    <div className="space-y-2">
                      <Skeleton className="h-10 w-2/3" />
                      <Skeleton className="ml-auto h-10 w-1/2" />
                    </div>
                  )}
                  {messagesQuery.isError && (
                    <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
                      {(messagesQuery.error as Error).message}
                    </p>
                  )}
                  {!messagesQuery.isLoading && messages.length === 0 && (
                    <p className="py-10 text-center text-[11px] text-muted">
                      还没有消息，发送第一条消息开始沟通。
                    </p>
                  )}
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={cn("flex", message.mine ? "justify-end" : "justify-start")}
                    >
                      <div
                        className={cn(
                          "max-w-[78%] rounded-xl border px-3 py-2",
                          message.mine
                            ? "border-primary bg-primary-soft text-ink"
                            : "border-line bg-surface text-ink",
                        )}
                      >
                        <p className="whitespace-pre-wrap break-words text-xs leading-relaxed">
                          {message.content}
                        </p>
                        <p className="mt-1 text-[10px] tabular-nums text-muted">
                          {formatShortDateTime(message.created_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="border-t border-line px-4 py-3">
                  {error && (
                    <p className="mb-2 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
                      {error}
                    </p>
                  )}
                  <div className="flex items-end gap-2">
                    <Textarea
                      value={draft}
                      onChange={(event) => setDraft(event.target.value)}
                      placeholder="输入消息，Enter 发送，Shift + Enter 换行"
                      onKeyDown={(event) => {
                        if (event.key === "Enter" && !event.shiftKey) {
                          event.preventDefault();
                          submit();
                        }
                      }}
                    />
                    <Button
                      loading={sendMutation.isPending}
                      disabled={!canSend}
                      onClick={submit}
                    >
                      发送
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-1 items-center justify-center">
                <p className="text-xs text-muted">选择左侧会话开始沟通</p>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
