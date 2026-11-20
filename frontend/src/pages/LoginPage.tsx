import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { homePath, useAuth } from "../lib/auth";
import { Button, Field, Input } from "../components/ui";

const DEMOS = [
  { label: "求职者 张三", username: "zhangsan", note: "已挂简历 · 可演示匹配" },
  { label: "招聘方 李 HR", username: "hr-li", note: "星澜科技 · 在招岗位" },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("zhangsan");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(0);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(username.trim(), password);
      navigate(homePath(user.role), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败，请重试");
      setShake((n) => n + 1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-[#0B1230] p-12 text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -left-24 top-1/3 h-72 w-72 rounded-full bg-primary/30 blur-[90px]" />
        <div className="pointer-events-none absolute -right-24 top-10 h-72 w-72 rounded-full bg-accent/25 blur-[100px]" />

        <div className="relative flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-sm font-bold ring-1 ring-white/20">
            JC
          </div>
          <span className="text-lg font-semibold tracking-tight">JobCopilot</span>
        </div>

        <div className="relative mt-auto">
          <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/70">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            双 Agent · 招聘求职双边平台
          </p>
          <h1 className="max-w-md text-4xl font-semibold leading-[1.18] tracking-tight">
            让 AI 帮你
            <br />
            找到对的人，和对的岗位
          </h1>
          <p className="mt-5 max-w-md text-sm leading-relaxed text-white/60">
            自研 Agent Runtime 驱动：简历结构化解析、三段式匹配管线、跨会话长期记忆。
            求职者与招聘方各自拥有一位懂业务的 AI 助手。
          </p>

          <div className="mt-10 grid max-w-md grid-cols-3 gap-3">
            {[
              ["50", "在招岗位"],
              ["30", "候选简历"],
              ["3 段式", "匹配管线"],
            ].map(([value, label], index) => (
              <div
                key={label}
                className="animate-fade-up rounded-2xl border border-white/10 bg-white/[0.04] p-3.5"
                style={{ animationDelay: `${index * 70}ms` }}
              >
                <p className="text-lg font-semibold">{value}</p>
                <p className="mt-0.5 text-[11px] text-white/50">{label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="relative mt-12 text-[11px] text-white/35">
          学习项目 · 数据为演示用虚构内容 · 不做真实上线
        </p>
      </section>

      <section className="flex items-center justify-center bg-white px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-sm font-bold text-white">
              JC
            </div>
          </div>

          <h2 className="text-2xl font-semibold tracking-tight">登录 JobCopilot</h2>
          <p className="mt-1.5 text-sm text-muted">选择演示账号快速体验，或使用你的账号登录。</p>

          <form
            key={shake}
            onSubmit={submit}
            className={shake ? "mt-7 space-y-4 shake-once" : "mt-7 space-y-4"}
          >
            <Field label="用户名">
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="请输入用户名"
                autoComplete="username"
              />
            </Field>
            <Field label="密码">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="请输入密码"
                autoComplete="current-password"
              />
            </Field>

            {error && (
              <p className="rounded-xl bg-[#FDECEC] px-3.5 py-2.5 text-xs text-danger">{error}</p>
            )}

            <Button type="submit" loading={loading} className="w-full">
              登录
            </Button>
          </form>

          <div className="mt-6 rounded-2xl border border-line bg-slate-50/70 p-3">
            <p className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
              演示账号 · 密码 demo1234
            </p>
            <div className="grid gap-2">
              {DEMOS.map((demo) => (
                <button
                  key={demo.username}
                  type="button"
                  onClick={() => {
                    setUsername(demo.username);
                    setPassword("demo1234");
                  }}
                  className="flex items-center justify-between rounded-xl bg-white px-3 py-2 text-left transition-all hover:shadow-sm"
                  style={{ transitionTimingFunction: "var(--ease-out)" }}
                >
                  <span>
                    <span className="block text-xs font-medium text-ink">{demo.label}</span>
                    <span className="block text-[10px] text-muted">{demo.note}</span>
                  </span>
                  <span className="text-[11px] text-primary">填入</span>
                </button>
              ))}
            </div>
          </div>

          <p className="mt-6 text-center text-xs text-muted">
            还没有账号？
            <Link to="/register" className="ml-1 font-medium text-primary hover:underline">
              立即注册
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
