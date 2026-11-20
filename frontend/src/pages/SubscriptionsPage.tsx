import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { Subscription } from "../lib/types";
import { BellIcon, PlusIcon } from "../components/icons";
import { Badge, Button, Card, EmptyState, Field, Input, Skeleton, cn } from "../components/ui";

const CITIES = ["上海", "北京", "深圳", "杭州", "广州", "成都", "远程"];

const EMPTY_FORM = {
  name: "",
  keywords: "",
  location: "",
  salary_min: "",
  skills: "",
  match_score_min: "",
};

function toNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function SubscriptionsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const listQuery = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api.get<{ items: Subscription[] }>("/subscriptions"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<Subscription>("/subscriptions", {
        name: form.name.trim() || "我的岗位订阅",
        filters: {
          keywords: form.keywords.trim(),
          location: form.location,
          salary_min: toNumber(form.salary_min),
          skills: form.skills
            .split(/[,，]/)
            .map((item) => item.trim())
            .filter(Boolean),
          match_score_min: toNumber(form.match_score_min),
        },
      }),
    onSuccess: () => {
      setForm(EMPTY_FORM);
      setError("");
      setNotice("订阅已创建，新发布的匹配岗位会出现在通知里");
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "创建失败"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api.put<Subscription>(`/subscriptions/${id}`, { active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["subscriptions"] }),
    onError: (err) => setError(err instanceof ApiError ? err.message : "更新失败"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.del(`/subscriptions/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["subscriptions"] }),
    onError: (err) => setError(err instanceof ApiError ? err.message : "删除失败"),
  });

  const scanMutation = useMutation({
    mutationFn: () =>
      api.post<{ skipped: boolean; created: number; scanned: number }>("/subscriptions/scan"),
    onSuccess: (data) => {
      setError("");
      if (data.skipped) {
        setNotice("10 分钟内已扫描过，稍后再试");
      } else if (data.created > 0) {
        setNotice(`扫描完成：新增 ${data.created} 条岗位提醒`);
      } else {
        setNotice(`扫描完成：检查了 ${data.scanned} 个新岗位，暂无符合条件的机会`);
      }
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "扫描失败"),
  });

  const update = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const items = listQuery.data?.items || [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-8">
      <header className="flex flex-wrap items-end justify-between gap-3 animate-fade-up">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">
            Subscriptions
          </p>
          <h1 className="mt-1.5 text-[26px] font-semibold tracking-tight">岗位订阅</h1>
          <p className="mt-1 text-sm text-muted">
            保存筛选条件，新发布的匹配岗位会进入站内通知（同一岗位只提醒一次）。
          </p>
        </div>
        <Button
          variant="soft"
          loading={scanMutation.isPending}
          onClick={() => scanMutation.mutate()}
        >
          <BellIcon className="h-4 w-4" /> 立即扫描新岗位
        </Button>
      </header>

      {error && (
        <p className="mt-4 rounded-xl bg-[#FDECEC] px-4 py-3 text-xs text-danger">{error}</p>
      )}
      {notice && (
        <p className="mt-4 rounded-xl bg-[#EAF8F0] px-4 py-3 text-xs text-success">{notice}</p>
      )}

      <div className="mt-6 grid gap-5 lg:grid-cols-[360px_1fr]">
        <Card className="h-fit p-5">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted">新建订阅</p>
          <div className="mt-3 space-y-3.5">
            <Field label="订阅名称">
              <Input
                value={form.name}
                onChange={update("name")}
                placeholder="如：上海 Python 高薪岗"
              />
            </Field>
            <Field label="关键词" hint="匹配岗位标题、描述、公司或技能">
              <Input
                value={form.keywords}
                onChange={update("keywords")}
                placeholder="如 Python"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="城市">
                <select
                  className="input"
                  value={form.location}
                  onChange={(event) => setForm({ ...form, location: event.target.value })}
                >
                  <option value="">不限</option>
                  {CITIES.map((city) => (
                    <option key={city} value={city}>
                      {city}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="最低月薪（K）">
                <Input
                  value={form.salary_min}
                  onChange={update("salary_min")}
                  placeholder="如 25"
                />
              </Field>
            </div>
            <Field label="技能" hint="逗号分隔，命中任意一个即可">
              <Input
                value={form.skills}
                onChange={update("skills")}
                placeholder="FastAPI, MySQL"
              />
            </Field>
            <Field label="最低匹配分（选填）" hint="需要已有简历；不填则不做分数过滤">
              <Input
                value={form.match_score_min}
                onChange={update("match_score_min")}
                placeholder="如 70"
              />
            </Field>
            <Button
              className="w-full"
              loading={createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              <PlusIcon className="h-4 w-4" /> 创建订阅
            </Button>
          </div>
        </Card>

        <div className="space-y-3">
          {listQuery.isLoading &&
            Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-28 w-full" />
            ))}

          {!listQuery.isLoading && items.length === 0 && (
            <EmptyState
              title="还没有岗位订阅"
              description="创建订阅后，招聘方新发布的匹配岗位会自动进入右上角通知铃铛。"
            />
          )}

          <div className="space-y-3 stagger">
            {items.map((subscription) => (
              <Card key={subscription.id} className={cn("p-5", !subscription.active && "opacity-70")}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-sm font-semibold">{subscription.name}</h3>
                      <Badge tone={subscription.active ? "success" : "default"}>
                        {subscription.active ? "生效中" : "已暂停"}
                      </Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {subscription.filters.keywords && (
                        <span className="chip">关键词：{subscription.filters.keywords}</span>
                      )}
                      {subscription.filters.location && (
                        <span className="chip">城市：{subscription.filters.location}</span>
                      )}
                      {subscription.filters.salary_min != null && (
                        <span className="chip">≥ {subscription.filters.salary_min}K</span>
                      )}
                      {(subscription.filters.skills || []).map((skill) => (
                        <span key={skill} className="chip">
                          {skill}
                        </span>
                      ))}
                      {subscription.filters.match_score_min != null && (
                        <span className="chip chip-primary">
                          匹配分 ≥ {subscription.filters.match_score_min}
                        </span>
                      )}
                      {!subscription.filters.keywords &&
                        !subscription.filters.location &&
                        subscription.filters.salary_min == null &&
                        !(subscription.filters.skills || []).length && (
                          <span className="text-[11px] text-muted">全部新岗位</span>
                        )}
                    </div>
                    <p className="mt-2 text-[11px] text-slate-400">
                      上次扫描：
                      {subscription.last_checked_at
                        ? new Date(subscription.last_checked_at).toLocaleString("zh-CN")
                        : "尚未扫描"}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        toggleMutation.mutate({
                          id: subscription.id,
                          active: !subscription.active,
                        })
                      }
                    >
                      {subscription.active ? "暂停" : "启用"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-danger hover:bg-[#FDECEC]"
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        if (window.confirm(`删除订阅「${subscription.name}」？`)) {
                          deleteMutation.mutate(subscription.id);
                        }
                      }}
                    >
                      删除
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
