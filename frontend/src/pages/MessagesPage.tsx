import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { ChatMessage, ConversationSummary } from "../lib/types";
import { formatShortDateTime } from "../lib/format";
import { Button, Card, EmptyState, Skeleton, Textarea, cn } from "../components/ui";
import { MessageCard } from "../components/MessageCard";

function mergeMessages(current: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  if (incoming.length === 0) return current;
  const byId = new Map<number, ChatMessage>();
  for (const item of current) byId.set(item.id, item);
  for (const item of incoming) byId.set(item.id, item);
  return [...byId.values()].sort((a, b) => a.id - b.id);
}

export function MessagesPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const targetId = Number(searchParams.get("c")) || null;
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadedOlder, setLoadedOlder] = useState(false);
  const [olderHasMore, setOlderHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [olderError, setOlderError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const restoreScrollRef = useRef<{ height: number; top: number } | null>(null);
  const lastScrollKeyRef = useRef<string | null>(null);

  const listQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: () =>
      api.get<{ items: ConversationSummary[]; unread: number }>("/conversations"),
    refetchInterval: 15_000,
  });

  const items = listQuery.data?.items || [];
  const selected = items.find((item) => item.id === selectedId) || null;

  // 从岗位详情「立即沟通」或候选人看板跳转过来时，直接定位到指定会话
  useEffect(() => {
    if (targetId) setSelectedId(targetId);
  }, [targetId]);

  useEffect(() => {
    if (targetId) return; // 指定会话时不做兜底切换，等列表刷新后仍保留目标
    if (!selectedId && items.length > 0) {
      setSelectedId(items[0].id);
      return;
    }
    if (selectedId && items.length > 0 && !items.some((item) => item.id === selectedId)) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId, targetId]);

  const selectConversation = (conversationId: number) => {
    setSelectedId(conversationId);
    if (targetId) setSearchParams({}, { replace: true });
  };

  const messagesQuery = useQuery({
    queryKey: ["messages", selectedId],
    queryFn: () =>
      api.get<{ items: ChatMessage[]; has_more: boolean }>(
        `/conversations/${selectedId}/messages?limit=100`,
      ),
    enabled: Boolean(selectedId),
    refetchInterval: 5_000,
  });

  useEffect(() => {
    setMessages([]);
    setLoadedOlder(false);
    setOlderHasMore(false);
    setOlderError("");
    lastScrollKeyRef.current = null;
  }, [selectedId]);

  useEffect(() => {
    const latest = messagesQuery.data?.items;
    if (latest) setMessages((prev) => mergeMessages(prev, latest));
  }, [messagesQuery.data]);

  const hasOlder = loadedOlder ? olderHasMore : Boolean(messagesQuery.data?.has_more);
  const lastMessageId = messages.length > 0 ? messages[messages.length - 1].id : null;

  const loadOlder = async () => {
    if (!selectedId || messages.length === 0 || loadingOlder) return;
    const node = scrollRef.current;
    const snapshot = node
      ? { height: node.scrollHeight, top: node.scrollTop }
      : null;
    setLoadingOlder(true);
    setOlderError("");
    try {
      const data = await api.get<{ items: ChatMessage[]; has_more: boolean }>(
        `/conversations/${selectedId}/messages?limit=100&before_id=${messages[0].id}`,
      );
      if (snapshot) restoreScrollRef.current = snapshot;
      setMessages((prev) => mergeMessages(prev, data.items));
      setLoadedOlder(true);
      setOlderHasMore(data.has_more);
    } catch (err) {
      setOlderError(err instanceof ApiError ? err.message : "加载更早消息失败");
    } finally {
      setLoadingOlder(false);
    }
  };

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
    if (node && restoreScrollRef.current) {
      const { height, top } = restoreScrollRef.current;
      restoreScrollRef.current = null;
      node.scrollTop = node.scrollHeight - height + top;
    }
  }, [messages]);

  // 切换会话或最后一条消息变化时滚到底部；向前翻页不打断阅读位置
  useEffect(() => {
    const key = `${selectedId}:${lastMessageId}`;
    if (lastScrollKeyRef.current === key) return;
    lastScrollKeyRef.current = key;
    const node = scrollRef.current;
    if (node && lastMessageId !== null) node.scrollTop = node.scrollHeight;
  }, [selectedId, lastMessageId]);

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
            ? "与候选人的沟通记录，含投递会话与主动联系。"
            : "与招聘方的沟通记录，可从岗位详情直接发起沟通。"}
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
                  onClick={() => selectConversation(item.id)}
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
                  <span className="truncate text-[11px] text-muted">
                    {item.job_title || "主动沟通"}
                  </span>
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
                      {selected.job_title || "主动沟通"}
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
                  {olderError && (
                    <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
                      {olderError}
                    </p>
                  )}
                  {messages.length > 0 && (
                    <div className="flex justify-center pb-1">
                      {hasOlder ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          loading={loadingOlder}
                          onClick={() => void loadOlder()}
                        >
                          加载更早消息
                        </Button>
                      ) : (
                        <span className="text-[10px] text-muted">已经是最早的消息</span>
                      )}
                    </div>
                  )}
                  {messages.map((message) =>
                    message.kind !== "text" && message.card ? (
                      <MessageCard
                        key={message.id}
                        message={message}
                        role={user?.role === "employer" ? "employer" : "seeker"}
                      />
                    ) : (
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
                    ),
                  )}
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
