import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Job, JobDiagnosis, JobIntent } from "../lib/types";
import { CITIES, CITY_DISTRICTS, JOB_CATEGORIES, JOB_TYPES } from "../lib/jobMeta";
import { JobCategoryPicker } from "./JobCategoryPicker";
import { Button } from "./ui";
import { cn } from "./ui";

/**
 * 岗位定位面板：设置求职意向（目标职位/方向/城市/薪资）+ 定位诊断（我适合什么方向）。
 * 意向存进简历的 structured.expectations，保存后重算向量并影响推荐排序。
 */
export function JobIntentPanel({
  jobs,
  onSaved,
}: {
  jobs: Job[];
  onSaved?: () => void;
}) {
  const queryClient = useQueryClient();
  const intentQuery = useQuery({
    queryKey: ["job-intent"],
    queryFn: () => api.get<JobIntent>("/resumes/intent"),
  });

  const [targetTitle, setTargetTitle] = useState("");
  const [category, setCategory] = useState("");
  const [subcategory, setSubcategory] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [subcategories, setSubcategories] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [districts, setDistricts] = useState<Record<string, string[]>>({});
  const [activeCity, setActiveCity] = useState("");
  const [salaryMin, setSalaryMin] = useState("");
  const [salaryMax, setSalaryMax] = useState("");
  const [jobTypes, setJobTypes] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [diagnosis, setDiagnosis] = useState<JobDiagnosis | null>(null);

  // 首次拿到意向后回填表单
  useEffect(() => {
    const data = intentQuery.data;
    if (!data) return;
    setTargetTitle(data.target_title || "");
    setCategories(data.categories || []);
    setSubcategories(data.subcategories || []);
    setLocations(data.locations || []);
    setDistricts(data.districts || {});
    setSalaryMin(data.salary_min != null ? String(data.salary_min) : "");
    setSalaryMax(data.salary_max != null ? String(data.salary_max) : "");
    setJobTypes(data.job_types || []);
  }, [intentQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put<JobIntent>("/resumes/intent", {
        target_title: targetTitle.trim(),
        categories,
        subcategories,
        locations,
        districts,
        salary_min: salaryMin ? Number(salaryMin) : null,
        salary_max: salaryMax ? Number(salaryMax) : null,
        job_types: jobTypes,
      }),
    onSuccess: (data) => {
      setNotice("求职意向已保存，岗位推荐会按新定位重新排序");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["job-intent"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["resume"] });
      onSaved?.();
      window.setTimeout(() => setNotice(""), 3500);
      void data;
    },
    onError: (err) => setError(err instanceof Error ? err.message : "保存失败"),
  });

  const diagnoseMutation = useMutation({
    mutationFn: () =>
      api.post<JobDiagnosis>("/resumes/diagnose", {
        category: category || null,
        subcategory: subcategory || null,
      }),
    onSuccess: (data) => {
      setDiagnosis(data);
      setError("");
    },
    onError: (err) => setError(err instanceof Error ? err.message : "定位诊断失败"),
  });

  const toggle = (list: string[], set: (v: string[]) => void, value: string, max = 3) => {
    set(
      list.includes(value)
        ? list.filter((v) => v !== value)
        : list.length >= max
          ? [...list.slice(1), value]
          : [...list, value],
    );
  };

  return (
    <div className="space-y-4">
      {/* 意向设置 */}
      <section className="rounded-xl border border-line bg-surface p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold text-muted">岗位定位</p>
            <p className="mt-0.5 text-[11px] text-muted">
              设定目标职位、方向、城市与薪资，推荐与匹配会按此排序；留空则沿用简历中解析出的意向
            </p>
          </div>
          {intentQuery.data && !intentQuery.data.has_resume && (
            <span className="shrink-0 rounded-md border border-warning bg-warning-soft px-2 py-0.5 text-[10px] text-warning">
              尚未有简历
            </span>
          )}
        </div>

        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-[11px] text-muted">目标职位</span>
            <input
              className="input mt-1 w-full"
              placeholder="如 后端开发工程师、算法工程师"
              value={targetTitle}
              maxLength={64}
              onChange={(e) => setTargetTitle(e.target.value)}
            />
          </label>

          <div>
            <span className="text-[11px] text-muted">岗位类别（最多 3 个）</span>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {JOB_CATEGORIES.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggle(categories, setCategories, c)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-[11px] transition-colors",
                    categories.includes(c)
                      ? "border-primary bg-primary-soft font-medium text-primary"
                      : "border-line text-muted hover:text-ink",
                  )}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-muted">具体方向</span>
            <JobCategoryPicker
              className="w-[240px]"
              jobs={jobs}
              category={category}
              subcategory={subcategory}
              onChange={(c, s) => {
                setCategory(c);
                setSubcategory(s);
              }}
              placeholder="选类别与方向后点「添加」"
            />
            <Button
              size="sm"
              variant="ghost"
              disabled={!category || !subcategory}
              onClick={() => {
                if (!subcategory || subcategories.includes(subcategory)) return;
                toggle(subcategories, setSubcategories, subcategory);
                if (!categories.includes(category)) toggle(categories, setCategories, category);
                setSubcategory("");
              }}
            >
              添加
            </Button>
          </div>
          {subcategories.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {subcategories.map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center gap-1 rounded-md bg-primary-soft px-2 py-0.5 text-[11px] text-primary"
                >
                  {s}
                  <button
                    type="button"
                    className="text-primary/60 hover:text-primary"
                    onClick={() => setSubcategories(subcategories.filter((v) => v !== s))}
                    aria-label={`移除 ${s}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}

          <div>
            <span className="text-[11px] text-muted">期望城市（可多选）</span>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {CITIES.map((city) => (
                <button
                  key={city}
                  type="button"
                  onClick={() => {
                    const next = locations.includes(city)
                      ? locations.filter((c) => c !== city)
                      : [...locations, city];
                    setLocations(next);
                    // 取消城市时同步丢掉它的区偏好
                    const nextDistricts = { ...districts };
                    if (!next.includes(city)) delete nextDistricts[city];
                    setDistricts(nextDistricts);
                    if (activeCity === city) setActiveCity("");
                  }}
                  className={cn(
                    "rounded-md border px-2.5 py-1 text-[11px] transition-colors",
                    locations.includes(city)
                      ? "border-primary bg-primary-soft font-medium text-primary"
                      : "border-line text-muted hover:text-ink",
                  )}
                >
                  {city}
                </button>
              ))}
            </div>
          </div>

          {/* 区级定位：只对已选城市展示 */}
          {locations.filter((c) => (CITY_DISTRICTS[c] || []).length > 0).length > 0 && (
            <div>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-muted">具体区域</span>
                {locations
                  .filter((c) => (CITY_DISTRICTS[c] || []).length > 0)
                  .map((city) => {
                      const picked = (districts[city] || []).length;
                      return (
                        <button
                          key={city}
                          type="button"
                          onClick={() => setActiveCity(activeCity === city ? "" : city)}
                          className={cn(
                            "rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                            activeCity === city
                              ? "border-primary bg-primary-soft font-medium text-primary"
                              : "border-line text-muted hover:text-ink",
                          )}
                        >
                          {city}
                          {picked > 0 && (
                            <span className="ml-1 tabular-nums text-primary">{picked}</span>
                          )}
                        </button>
                      );
                    })}
              </div>

              {activeCity && (CITY_DISTRICTS[activeCity] || []).length > 0 && (
                <div className="mt-2 rounded-lg border border-line bg-neutral-soft p-2.5">
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] text-muted">
                      {activeCity} · 可多选，选了区会优先推荐该区域的岗位
                    </p>
                    {(districts[activeCity] || []).length > 0 && (
                      <button
                        type="button"
                        className="text-[11px] text-muted hover:text-ink"
                        onClick={() => {
                          const next = { ...districts };
                          delete next[activeCity];
                          setDistricts(next);
                        }}
                      >
                        清空
                      </button>
                    )}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(CITY_DISTRICTS[activeCity] || []).map((d) => {
                      const picked = (districts[activeCity] || []).includes(d);
                      return (
                        <button
                          key={d}
                          type="button"
                          onClick={() => {
                            const current = districts[activeCity] || [];
                            const nextList = picked
                              ? current.filter((x) => x !== d)
                              : [...current, d].slice(-8);
                            setDistricts({ ...districts, [activeCity]: nextList });
                          }}
                          className={cn(
                            "rounded-md border px-2 py-0.5 text-[11px] transition-colors",
                            picked
                              ? "border-primary bg-surface font-medium text-primary"
                              : "border-line bg-surface text-muted hover:text-ink",
                          )}
                        >
                          {d}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          <div>
            <span className="text-[11px] text-muted">期望月薪（K）</span>
            <div className="mt-1 flex items-center gap-2">
              <input
                className="input w-full"
                type="number"
                min={0}
                placeholder="20"
                value={salaryMin}
                onChange={(e) => setSalaryMin(e.target.value)}
              />
              <span className="text-muted">—</span>
              <input
                className="input w-full"
                type="number"
                min={0}
                placeholder="35"
                value={salaryMax}
                onChange={(e) => setSalaryMax(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-muted">工作类型</span>
            {JOB_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => toggle(jobTypes, setJobTypes, t, 2)}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-[11px] transition-colors",
                  jobTypes.includes(t)
                    ? "border-primary bg-primary-soft font-medium text-primary"
                    : "border-line text-muted hover:text-ink",
                )}
              >
                {t}
              </button>
            ))}
          </div>

          {error && (
            <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-xs text-danger">
              {error}
            </p>
          )}
          {notice && (
            <p className="rounded-lg border border-success bg-success-soft px-3 py-2 text-xs text-success">
              {notice}
            </p>
          )}

          <div className="flex items-center gap-2 pt-1">
            <Button
              size="sm"
              loading={saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              保存定位
            </Button>
            <Button
              size="sm"
              variant="ghost"
              loading={diagnoseMutation.isPending}
              disabled={!intentQuery.data?.has_resume}
              onClick={() => diagnoseMutation.mutate()}
            >
              我适合做什么
            </Button>
          </div>
        </div>
      </section>

      {/* 定位诊断结果 */}
      {diagnosis && (
        <section className="rounded-xl border border-line bg-surface p-5">
          <p className="text-[11px] font-semibold text-muted">定位诊断</p>
          <p className="mt-2 text-sm leading-relaxed">{diagnosis.positioning}</p>

          <div className="mt-4 space-y-2">
            {diagnosis.fits.map((fit) => (
              <div key={`${fit.category}-${fit.subcategory}`} className="border-b border-line pb-3 last:border-b-0">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">
                    {fit.category} · {fit.subcategory || "全部方向"}
                  </p>
                  <span className="shrink-0 text-sm tabular-nums text-primary">
                    {fit.fit_score}
                    <span className="ml-0.5 text-[10px] text-muted">/100</span>
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-muted">{fit.reason}</p>
                {fit.gap && (
                  <p className="mt-1 text-xs leading-relaxed text-warning">差距：{fit.gap}</p>
                )}
              </div>
            ))}
          </div>

          {diagnosis.risks.length > 0 && (
            <div className="mt-4">
              <p className="text-[11px] font-semibold text-muted">风险</p>
              <ul className="mt-1 space-y-1">
                {diagnosis.risks.map((r) => (
                  <li key={r} className="text-xs leading-relaxed text-muted">
                    · {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {diagnosis.next_steps.length > 0 && (
            <div className="mt-4">
              <p className="text-[11px] font-semibold text-muted">下一步</p>
              <ol className="mt-1 space-y-1">
                {diagnosis.next_steps.map((s, i) => (
                  <li key={s} className="text-xs leading-relaxed text-muted">
                    {i + 1}. {s}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
