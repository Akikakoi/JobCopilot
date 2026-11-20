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
}

const SEEKER_NAV: NavItem[] = [
  { to: "/seeker/jobs", label: "找岗位", icon: BriefcaseIcon },
  { to: "/seeker/chat", label: "AI 求职助手", icon: ChatIcon },
  { to: "/seeker/interview", label: "面试训练", icon: MicIcon },
  { to: "/seeker/subscriptions", label: "岗位订阅", icon: BellIcon },
  { to: "/seeker/resume", label: "我的简历", icon: FileIcon },
  { to: "/seeker/applications", label: "我的投递", icon: SendIcon },
];

const EMPLOYER_NAV: NavItem[] = [
  { to: "/employer/jobs", label: "岗位管理", icon: BriefcaseIcon },
  { to: "/employer/board", label: "候选人看板", icon: BoardIcon },
  { to: "/employer/chat", label: "AI 招聘助手", icon: ChatIcon },
];

function todayLabel() {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date());
}

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

  const signOut = () => {
    logout();
    navigate("/login");
  };

  /* ---------------- 求职者：顶部导航 + 居中内容 ---------------- */
  if (user.role === "seeker") {
    return (
      <div className="theme-seeker flex h-full flex-col bg-bg">
        <header className="shrink-0 border-b border-line bg-surface">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 md:px-8">
            <NavLink to="/seeker/jobs" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-xs font-bold text-white">
                JC
              </div>
              <span className="text-[15px] font-semibold">JobCopilot</span>
            </NavLink>

            <nav className="hidden h-14 items-center gap-0.5 md:flex">
              {SEEKER_NAV.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "flex h-14 items-center border-b-2 px-3 text-[13px] transition-colors",
                      isActive
                        ? "border-primary font-semibold text-primary"
                        : "border-transparent text-muted hover:text-ink",
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <NotificationBell align="right" />
              <span className="hidden h-4 w-px bg-line md:block" />
              <span className="hidden text-xs text-muted md:inline">{user.display_name}</span>
              <button onClick={signOut} className="p-1.5 text-muted transition-colors hover:text-danger" title="退出登录">
                <LogoutIcon className="h-4 w-4" />
              </button>
            </div>
          </div>

          <nav className="flex items-center gap-4 overflow-x-auto border-t border-line px-4 py-2 md:hidden">
            {SEEKER_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "whitespace-nowrap text-xs",
                    isActive ? "font-semibold text-primary" : "text-muted",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="app-scroll min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    );
  }

  /* ---------------- 招聘方：左侧栏 + 全宽工作区 ---------------- */
  return (
    <div className="theme-employer flex h-full bg-bg">
      <aside className="hidden w-[204px] shrink-0 flex-col border-r border-line bg-surface px-3 py-5 md:flex">
        <div className="flex items-center gap-2.5 px-1">
          <div className="flex h-7 w-7 items-center justify-center rounded-sm bg-primary text-[11px] font-bold text-white">
            JC
          </div>
          <div>
            <p className="text-[13px] font-semibold leading-tight">JobCopilot</p>
            <p className="mt-0.5 text-[10px] text-muted">招聘工作台</p>
          </div>
        </div>

        <div className="mt-5 border-y border-line px-1 py-3">
          <p className="text-[10px] text-muted">当前公司</p>
          <p className="mt-1 truncate text-[13px] font-semibold">
            {user.company_name || "未填写公司"}
          </p>
        </div>

        <nav className="mt-3 space-y-0.5">
          {EMPLOYER_NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 border-l-2 py-2.5 pl-2.5 pr-2 text-[13px] transition-colors",
                    isActive
                      ? "border-primary bg-neutral-soft font-semibold text-ink"
                      : "border-transparent text-muted hover:bg-neutral-soft hover:text-ink",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted")}
                    />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-line pt-3">
          <div className="flex items-center gap-2.5 px-1">
            <div className="flex h-7 w-7 items-center justify-center rounded-full border border-line bg-neutral-soft text-[11px] font-semibold">
              {user.display_name.slice(0, 1)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium">{user.display_name}</p>
              <p className="truncate text-[10px] text-muted">{user.company_name || "招聘方"}</p>
            </div>
            <button
              onClick={signOut}
              className="p-1 text-muted transition-colors hover:text-danger"
              title="退出登录"
            >
              <LogoutIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="hidden items-center justify-between border-b border-line bg-surface px-6 py-2.5 md:flex">
          <p className="text-[13px] font-semibold">{user.company_name || "招聘工作台"}</p>
          <p className="text-xs tabular-nums text-muted">{todayLabel()}</p>
        </header>

        <header className="flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3 md:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-sm bg-primary text-[11px] font-bold text-white">
              JC
            </div>
            <span className="text-sm font-semibold">JobCopilot</span>
          </div>
          <div className="flex items-center gap-3 overflow-x-auto">
            {EMPLOYER_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "whitespace-nowrap text-xs",
                    isActive ? "font-semibold text-ink" : "text-muted",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            <button onClick={signOut} className="p-1 text-muted" title="退出登录">
              <LogoutIcon className="h-4 w-4" />
            </button>
          </div>
        </header>

        <main className="app-scroll min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
