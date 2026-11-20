import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AppNotification } from "../lib/types";
import { BellIcon } from "./icons";
import { Button, cn } from "./ui";

const PANEL_WIDTH = 320;
const GAP = 8;

export function NotificationBell({ align = "right" }: { align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<{ items: AppNotification[]; unread: number }>("/notifications?limit=20"),
    refetchInterval: 30_000,
  });

  const updatePosition = useCallback(() => {
    const rect = buttonRef.current?.getBoundingClientRect();
    if (!rect) return;
    const preferred =
      align === "left" ? rect.left : rect.right - PANEL_WIDTH;
    const maxLeft = window.innerWidth - PANEL_WIDTH - GAP;
    setPosition({
      top: rect.bottom + GAP,
      left: Math.max(GAP, Math.min(preferred, maxLeft)),
    });
  }, [align]);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    };
    const onResize = () => updatePosition();
    const onScroll = () => setOpen(false);
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, updatePosition]);

  const readMutation = useMutation({
    mutationFn: (id: number) => api.post(`/notifications/${id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const readAllMutation = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const unread = query.data?.unread || 0;
  const items = query.data?.items || [];

  const openNotification = async (notification: AppNotification) => {
    if (!notification.read) {
      readMutation.mutate(notification.id);
    }
    setOpen(false);
    const jobId = notification.payload?.job_id;
    if (jobId) {
      navigate(`/seeker/jobs/${jobId}`);
    }
  };

  const panel =
    open && position
      ? createPortal(
          <div
            ref={panelRef}
            style={{
              position: "fixed",
              top: position.top,
              left: position.left,
              width: PANEL_WIDTH,
              zIndex: 9999,
            }}
            className="animate-scale-in overflow-hidden rounded-2xl border border-line bg-white shadow-[0_24px_48px_-16px_rgba(15,23,42,0.28)]"
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <div className="flex items-center gap-2">
                <p className="text-xs font-semibold">通知</p>
                {unread > 0 && (
                  <span className="rounded-full bg-[#FDECEC] px-1.5 py-0.5 text-[10px] font-medium text-danger">
                    {unread} 条未读
                  </span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                disabled={unread === 0 || readAllMutation.isPending}
                onClick={() => readAllMutation.mutate()}
              >
                全部已读
              </Button>
            </div>

            <div className="max-h-[min(360px,60vh)] overflow-y-auto">
              {query.isLoading && (
                <p className="px-4 py-8 text-center text-[11px] text-muted">加载中…</p>
              )}
              {!query.isLoading && items.length === 0 && (
                <div className="px-4 py-10 text-center">
                  <p className="text-xs font-medium text-slate-600">暂无通知</p>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted">
                    创建岗位订阅后，新发布的匹配岗位会在这里提醒你。
                  </p>
                </div>
              )}
              {items.map((notification) => (
                <button
                  key={notification.id}
                  onClick={() => void openNotification(notification)}
                  className={cn(
                    "flex w-full gap-2.5 border-b border-line/70 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-slate-50",
                    !notification.read && "bg-[#F7F9FF]",
                  )}
                >
                  <span
                    className={cn(
                      "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                      notification.read ? "bg-slate-300" : "bg-primary",
                    )}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-medium leading-relaxed text-ink">
                      {notification.title}
                    </span>
                    <span className="mt-0.5 flex flex-wrap gap-x-2 text-[10px] text-muted">
                      {notification.payload?.location && <span>{notification.payload.location}</span>}
                      {notification.payload?.salary_min != null && (
                        <span>
                          {notification.payload.salary_min}-{notification.payload.salary_max}K
                        </span>
                      )}
                      {notification.payload?.match_score != null && (
                        <span className="text-primary">
                          匹配 {Math.round(notification.payload.match_score)} 分
                        </span>
                      )}
                    </span>
                    {notification.payload?.subscription_name && (
                      <span className="mt-0.5 block text-[10px] text-slate-400">
                        来自订阅「{notification.payload.subscription_name}」
                      </span>
                    )}
                  </span>
                </button>
              ))}
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <button
        ref={buttonRef}
        onClick={() => setOpen((value) => !value)}
        className="relative rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-ink"
        title="通知"
        aria-label="通知"
      >
        <BellIcon className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-danger px-1 text-[9px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {panel}
    </>
  );
}
