import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { CompanyInfo } from "../lib/types";
import { BuildingIcon, SettingsIcon } from "../components/icons";
import { Button, Card, Field, Input, Textarea, cn } from "../components/ui";

export function SettingsPage() {
  const { user, refreshUser } = useAuth();

  const [displayName, setDisplayName] = useState(user?.display_name || "");
  const [profileNotice, setProfileNotice] = useState("");
  const [profileError, setProfileError] = useState("");

  const [company, setCompany] = useState({ name: "", industry: "", description: "" });
  const [companyNotice, setCompanyNotice] = useState("");
  const [companyError, setCompanyError] = useState("");

  const [password, setPassword] = useState({
    old_password: "",
    new_password: "",
    confirm: "",
  });
  const [passwordNotice, setPasswordNotice] = useState("");
  const [passwordError, setPasswordError] = useState("");

  useEffect(() => {
    if (user) setDisplayName(user.display_name);
  }, [user?.display_name]);

  const companyQuery = useQuery({
    queryKey: ["my-company"],
    queryFn: () => api.get<CompanyInfo>("/companies/mine"),
    enabled: user?.role === "employer",
  });

  useEffect(() => {
    if (companyQuery.data) {
      setCompany({
        name: companyQuery.data.name,
        industry: companyQuery.data.industry,
        description: companyQuery.data.description,
      });
    }
  }, [companyQuery.data]);

  const profileMutation = useMutation({
    mutationFn: () => api.put("/auth/me", { display_name: displayName.trim() }),
    onSuccess: async () => {
      setProfileError("");
      setProfileNotice("显示名已更新");
      await refreshUser();
    },
    onError: (err) => {
      setProfileNotice("");
      setProfileError(err instanceof ApiError ? err.message : "资料保存失败");
    },
  });

  const companyMutation = useMutation({
    mutationFn: () =>
      api.put("/companies/mine", {
        name: company.name.trim(),
        industry: company.industry.trim(),
        description: company.description.trim(),
      }),
    onSuccess: async () => {
      setCompanyError("");
      setCompanyNotice("公司资料已更新");
      await refreshUser();
    },
    onError: (err) => {
      setCompanyNotice("");
      setCompanyError(err instanceof ApiError ? err.message : "公司资料保存失败");
    },
  });

  const passwordMutation = useMutation({
    mutationFn: () =>
      api.post("/auth/change-password", {
        old_password: password.old_password,
        new_password: password.new_password,
      }),
    onSuccess: () => {
      setPasswordError("");
      setPasswordNotice("密码已修改，下次登录请使用新密码");
      setPassword({ old_password: "", new_password: "", confirm: "" });
    },
    onError: (err) => {
      setPasswordNotice("");
      setPasswordError(err instanceof ApiError ? err.message : "密码修改失败");
    },
  });

  if (!user) return null;

  const isEmployer = user.role === "employer";
  const wrapper = isEmployer ? "px-6 py-5" : "mx-auto max-w-3xl px-4 py-8 md:px-8";

  const submitPassword = () => {
    setPasswordError("");
    setPasswordNotice("");
    if (password.new_password.length < 6) {
      setPasswordError("新密码至少 6 位");
      return;
    }
    if (password.new_password !== password.confirm) {
      setPasswordError("两次输入的新密码不一致");
      return;
    }
    passwordMutation.mutate();
  };

  return (
    <div className={wrapper}>
      <header className={cn("animate-fade-up", isEmployer && "border-b border-line pb-3")}>
        <div className="flex items-center gap-2">
          <SettingsIcon className="h-4 w-4 text-muted" />
          <h1 className={isEmployer ? "text-base font-semibold" : "text-[26px] font-semibold tracking-tight"}>
            设置
          </h1>
        </div>
        <p className="mt-1 text-xs text-muted">管理个人资料、密码{isEmployer ? "与公司信息" : ""}。</p>
      </header>

      <div className="mt-5 space-y-4">
        <Card className="p-5">
          <p className="text-sm font-semibold">个人资料</p>
          <p className="mt-1 text-xs text-muted">登录用户名不可修改。</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Field label="用户名">
              <Input value={user.username} disabled />
            </Field>
            <Field label="显示名">
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="显示在界面右上角的名字"
              />
            </Field>
          </div>
          {profileError && (
            <p className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
              {profileError}
            </p>
          )}
          {profileNotice && (
            <p className="mt-3 rounded-lg border border-success bg-success-soft px-3 py-2 text-[11px] text-success">
              {profileNotice}
            </p>
          )}
          <div className="mt-4 flex justify-end">
            <Button
              size="sm"
              loading={profileMutation.isPending}
              disabled={!displayName.trim() || displayName.trim() === user.display_name}
              onClick={() => profileMutation.mutate()}
            >
              保存资料
            </Button>
          </div>
        </Card>

        {isEmployer && (
          <Card className="p-5">
            <div className="flex items-center gap-2">
              <BuildingIcon className="h-4 w-4 text-muted" />
              <p className="text-sm font-semibold">公司资料</p>
            </div>
            <p className="mt-1 text-xs text-muted">求职者会在公司主页看到这些信息。</p>
            {companyQuery.isLoading ? (
              <p className="mt-4 text-xs text-muted">加载中…</p>
            ) : (
              <div className="mt-4 space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="公司名称">
                    <Input
                      value={company.name}
                      onChange={(event) => setCompany({ ...company, name: event.target.value })}
                      placeholder="如 星澜科技"
                    />
                  </Field>
                  <Field label="所属行业">
                    <Input
                      value={company.industry}
                      onChange={(event) => setCompany({ ...company, industry: event.target.value })}
                      placeholder="如 互联网 / 智能制造"
                    />
                  </Field>
                </div>
                <Field label="公司简介" hint="建议 50-200 字，说明业务与团队。">
                  <Textarea
                    value={company.description}
                    onChange={(event) =>
                      setCompany({ ...company, description: event.target.value })
                    }
                    placeholder="介绍公司业务、团队规模、技术方向……"
                  />
                </Field>
                {companyError && (
                  <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
                    {companyError}
                  </p>
                )}
                {companyNotice && (
                  <p className="rounded-lg border border-success bg-success-soft px-3 py-2 text-[11px] text-success">
                    {companyNotice}
                  </p>
                )}
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    loading={companyMutation.isPending}
                    disabled={!company.name.trim()}
                    onClick={() => companyMutation.mutate()}
                  >
                    保存公司资料
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}

        <Card className="p-5">
          <p className="text-sm font-semibold">修改密码</p>
          <p className="mt-1 text-xs text-muted">修改成功后，当前登录状态仍然有效。</p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <Field label="原密码">
              <Input
                type="password"
                value={password.old_password}
                onChange={(event) =>
                  setPassword({ ...password, old_password: event.target.value })
                }
                placeholder="当前密码"
              />
            </Field>
            <Field label="新密码" hint="至少 6 位">
              <Input
                type="password"
                value={password.new_password}
                onChange={(event) =>
                  setPassword({ ...password, new_password: event.target.value })
                }
                placeholder="新密码"
              />
            </Field>
            <Field label="确认新密码">
              <Input
                type="password"
                value={password.confirm}
                onChange={(event) => setPassword({ ...password, confirm: event.target.value })}
                placeholder="再次输入新密码"
              />
            </Field>
          </div>
          {passwordError && (
            <p className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
              {passwordError}
            </p>
          )}
          {passwordNotice && (
            <p className="mt-3 rounded-lg border border-success bg-success-soft px-3 py-2 text-[11px] text-success">
              {passwordNotice}
            </p>
          )}
          <div className="mt-4 flex justify-end">
            <Button
              size="sm"
              loading={passwordMutation.isPending}
              disabled={!password.old_password || !password.new_password || !password.confirm}
              onClick={submitPassword}
            >
              修改密码
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
