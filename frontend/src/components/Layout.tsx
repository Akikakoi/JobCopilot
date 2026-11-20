import { useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import {
  BoardIcon,
  BriefcaseIcon,
  ChatIcon,
  FileIcon,
  LogoutIcon,
  MicIcon,
  SendIcon,
  BellIcon,
} from "./icons";
import { NotificationBell } from "./NotificationBell";
import { cn } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: typeof BriefcaseIcon;
  hint: string;
}

const SEEKER_NAV: NavItem[] = [
  { to: "/seeker/jobs", label: "找岗位", icon: BriefcaseIcon, hint: "搜索 · 匹配" },
  { to: "/seeker/chat", label: "AI 求职助手", icon: ChatIcon, hint: "对话找工作" },
  { to: "/seeker/interview", label: "面试训练", icon: MicIcon, hint: "模拟 · 报告" },
  { to: "/seeker/subscriptions", label: "岗位订阅", icon: BellIcon, hint: "新岗位提醒" },
  { to: "/seeker/resume", label: "我的简历", icon: FileIcon, hint: "解析 · 结构化" },
  { to: "/seeker/applications", label: "我的投递", icon: SendIcon, hint: "进度跟踪" },
];

const EMPLOYER_NAV: NavItem[] = [
  { to: "/employer/jobs", label: "岗位管理", icon: BriefcaseIcon, hint: "发布 · 维护" },
  { to: "/employer/board", label: "候选人看板", icon: BoardIcon, hint: "筛选 · 推进" },
  { to: "/employer/chat", label: "AI 招聘助手", icon: ChatIcon, hint: "对话招人" },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // 登录后触发一次订阅扫描（服务端 10 分钟节流），随后刷新通知角标
  useEffect(() => {
    if (user?.role !== "seeker") return;
    api
      .post("/subscriptions/scan")
      .then(() => queryClient.invalidateQueries({ queryKey: ["notifications"] }))
      .catch(() => {
        /* 扫描失败不影响主流程 */
      });
  }, [user?.id, user?.role, queryClient]);

  if (!user) return null;

  const nav = user.role === "employer" ? EMPLOYER_NAV : SEEKER_NAV;

  return (
    <div className="flex h-full bg-bg">
      <aside className="relative z-30 hidden w-[248px] shrink-0 flex-col border-r border-line bg-white/80 px-4 py-6 backdrop-blur md:flex">
        <div className="flex items-center gap-2.5 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-sm font-bold text-white shadow-sm">
            JC
          </div>
          <div>
            <p className="text-[15px] font-semibold leading-tight tracking-tight">JobCopilot</p>
            <p className="text-[11px] text-muted">
              {user.role === "employer" ? "招聘方工作台" : "求职者空间"}
            </p>
          </div>
          {user.role === "seeker" && (
            <div className="ml-auto">
              <NotificationBell align="left" />
            </div>
          )}
        </div>

        <nav className="mt-8 space-y-1">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200",
                    isActive
                      ? "bg-[#EEF3FF] font-semibold text-primary"
                      : "text-slate-600 hover:bg-slate-50 hover:text-ink",
                  )
                }
                style={{ transitionTimingFunction: "var(--ease-out)" }}
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn(
                        "h-[18px] w-[18px] shrink-0 transition-transform duration-200",
                        isActive ? "text-primary" : "text-slate-400 group-hover:text-slate-600",
                      )}
                    />
                    <span className="flex-1">{item.label}</span>
                    <span
                      className={cn(
                        "text-[10px]",
                        isActive ? "text-primary/60" : "text-slate-300",
                      )}
                    >
                      {item.hint}
                    </span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-auto">
          <div className="rounded-2xl border border-line bg-slate-50/80 p-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-sm font-semibold text-primary shadow-sm">
                {user.display_name.slice(0, 1)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink">{user.display_name}</p>
                <p className="truncate text-[11px] text-muted">
                  {user.role === "employer" ? user.company_name || "招聘方" : "求职者"}
                </p>
              </div>
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white hover:text-danger"
                title="退出登录"
              >
                <LogoutIcon className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="relative z-30 flex items-center justify-between gap-3 border-b border-line bg-white/70 px-4 py-3 backdrop-blur md:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-accent text-xs font-bold text-white">
              JC
            </div>
            <span className="text-sm font-semibold">JobCopilot</span>
          </div>
          <div className="flex items-center gap-1 overflow-x-auto">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs transition-colors",
                    isActive ? "bg-[#EEF3FF] font-semibold text-primary" : "text-slate-500",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            {user.role === "seeker" && <NotificationBell align="right" />}
            <button
              onClick={() => {
                logout();
                navigate("/login");
              }}
              className="rounded-lg p-1.5 text-slate-400"
              title="退出登录"
            >
              <LogoutIcon className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
