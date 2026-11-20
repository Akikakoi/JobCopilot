import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { homePath, useAuth } from "../lib/auth";
import { Button, Field, Input } from "../components/ui";

const DEMOS = [
  { label: "求职者 张三", username: "zhangsan", note: "已挂简历" },
  { label: "招聘方 李 HR", username: "hr-li", note: "星澜科技" },
];

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("zhangsan");
  const [password, setPassword] = useState("demo1234");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(username.trim(), password);
      navigate(homePath(user.role), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "登录失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="theme-seeker grid min-h-full bg-bg lg:grid-cols-[1.05fr_1fr]">
      <section className="hidden flex-col justify-between border-r border-line px-12 py-10 lg:flex">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
            JC
          </div>
          <span className="text-base font-semibold">JobCopilot</span>
        </div>

        <div>
          <h1 className="max-w-[380px] text-[34px] font-semibold leading-[1.25] tracking-tight">
            找到合适的岗位，
            <br />
            也找到合适的人。
          </h1>
          <p className="mt-4 max-w-[380px] text-sm leading-relaxed text-muted">
            求职者与招聘方各自拥有一位 AI 助手：解析简历、计算匹配分、准备面试、筛选候选人。
          </p>
        </div>

        <p className="text-[11px] text-muted">演示项目 · 数据为虚构内容</p>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-[360px]">
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-sm font-bold text-white">
              JC
            </div>
            <span className="text-base font-semibold">JobCopilot</span>
          </div>

          <h2 className="text-xl font-semibold tracking-tight">登录</h2>
          <p className="mt-1 text-xs text-muted">使用用户名和密码进入你的工作台。</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Field label="用户名">
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                placeholder="用户名"
              />
            </Field>
            <Field label="密码">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                placeholder="密码"
              />
            </Field>

            {error && (
              <p className="rounded-xl border border-danger bg-danger-soft px-3.5 py-2.5 text-xs text-danger">
                {error}
              </p>
            )}

            <Button type="submit" loading={loading} className="w-full">
              登录
            </Button>
          </form>

          <div className="mt-8 border-t border-line pt-4">
            <p className="mb-2 text-[11px] font-semibold text-muted">演示账号 · 密码 demo1234</p>
            <div className="divide-y divide-line border-y border-line">
              {DEMOS.map((demo) => (
                <button
                  key={demo.username}
                  type="button"
                  onClick={() => {
                    setUsername(demo.username);
                    setPassword("demo1234");
                  }}
                  className="flex w-full items-center justify-between py-2.5 text-left transition-colors hover:text-primary"
                >
                  <span>
                    <span className="block text-xs font-medium">{demo.label}</span>
                    <span className="block text-[11px] text-muted">{demo.note}</span>
                  </span>
                  <span className="text-[11px] text-primary">填入</span>
                </button>
              ))}
            </div>
          </div>

          <p className="mt-6 text-xs text-muted">
            还没有账号？
            <Link to="/register" className="ml-1 font-medium text-primary hover:underline">
              注册
            </Link>
          </p>
        </div>
      </section>
    </div>
  );
}
