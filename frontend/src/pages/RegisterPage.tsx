import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { homePath, useAuth } from "../lib/auth";
import type { Role } from "../lib/types";
import { Button, Field, Input, cn } from "../components/ui";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [role, setRole] = useState<Role>("seeker");
  const [form, setForm] = useState({
    username: "",
    password: "",
    display_name: "",
    company_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const update = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await register({
        username: form.username.trim(),
        password: form.password,
        role,
        display_name: form.display_name.trim() || form.username.trim(),
        company_name: role === "employer" ? form.company_name.trim() || undefined : undefined,
      });
      navigate(homePath(user.role), { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "注册失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-bg px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-7 flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-accent text-sm font-bold text-white">
            JC
          </div>
          <div>
            <p className="text-base font-semibold tracking-tight">JobCopilot</p>
            <p className="text-[11px] text-muted">创建账号，开始使用 AI 助手</p>
          </div>
        </div>

        <div className="card p-6">
          <h1 className="text-xl font-semibold tracking-tight">注册账号</h1>
          <p className="mt-1 text-xs text-muted">选择你的身份，注册后不可更改。</p>

          <div className="mt-4 grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
            {(
              [
                ["seeker", "我是求职者"],
                ["employer", "我是招聘方"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setRole(value)}
                className={cn(
                  "rounded-lg py-2 text-xs font-medium transition-all duration-200",
                  role === value ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink",
                )}
                style={{ transitionTimingFunction: "var(--ease-out)" }}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-4">
            <Field label="用户名" hint="2-32 位，用于登录">
              <Input value={form.username} onChange={update("username")} placeholder="如 zhangsan" />
            </Field>
            <Field label="密码" hint="至少 6 位">
              <Input
                type="password"
                value={form.password}
                onChange={update("password")}
                placeholder="设置登录密码"
              />
            </Field>
            <Field label="显示名">
              <Input
                value={form.display_name}
                onChange={update("display_name")}
                placeholder={role === "employer" ? "如 李 HR" : "如 张三"}
              />
            </Field>
            {role === "employer" && (
              <Field label="公司名称">
                <Input
                  value={form.company_name}
                  onChange={update("company_name")}
                  placeholder="如 星澜科技"
                />
              </Field>
            )}

            {error && (
              <p className="rounded-xl bg-[#FDECEC] px-3.5 py-2.5 text-xs text-danger">{error}</p>
            )}

            <Button type="submit" loading={loading} className="w-full">
              注册并进入
            </Button>
          </form>

          <p className="mt-5 text-center text-xs text-muted">
            已有账号？
            <Link to="/login" className="ml-1 font-medium text-primary hover:underline">
              返回登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
