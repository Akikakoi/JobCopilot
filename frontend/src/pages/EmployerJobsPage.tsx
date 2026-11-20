import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { Job } from "../lib/types";
import { ArrowRightIcon, PlusIcon } from "../components/icons";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Modal,
  Skeleton,
  STATUS_META,
  Textarea,
} from "../components/ui";

interface JobWithCount extends Job {
  applicant_count: number;
}

const EMPTY_FORM = {
  title: "",
  description: "",
  required_skills: "",
  preferred_skills: "",
  experience_min: "0",
  experience_max: "5",
  location: "上海",
  salary_min: "15",
  salary_max: "25",
};

export function EmployerJobsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState("");

  const jobsQuery = useQuery({
    queryKey: ["my-jobs"],
    queryFn: () => api.get<{ items: JobWithCount[] }>("/jobs/mine"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["my-jobs"] });
    queryClient.invalidateQueries({ queryKey: ["candidates"] });
  };

  const createMutation = useMutation({
    mutationFn: () =>
      api.post<Job>("/jobs", {
        title: form.title.trim(),
        description: form.description.trim(),
        required_skills: form.required_skills
          .split(/[,，]/)
          .map((item) => item.trim())
          .filter(Boolean),
        preferred_skills: form.preferred_skills
          .split(/[,，]/)
          .map((item) => item.trim())
          .filter(Boolean),
        experience_min: Number(form.experience_min) || 0,
        experience_max: Number(form.experience_max) || 0,
        location: form.location.trim() || "不限",
        salary_min: Number(form.salary_min) || 0,
        salary_max: Number(form.salary_max) || 0,
      }),
    onSuccess: () => {
      setOpen(false);
      setForm(EMPTY_FORM);
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "发布失败"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.put<Job>(`/jobs/${id}`, { status }),
    onSuccess: invalidate,
  });

  const update = (key: keyof typeof form) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((prev) => ({ ...prev, [key]: event.target.value }));

  const jobs = jobsQuery.data?.items || [];
  const openCount = jobs.filter((job) => job.status === "open").length;
  const totalApplicants = jobs.reduce((sum, job) => sum + job.applicant_count, 0);

  return (
    <div className="px-6 py-5">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3 animate-fade-up">
        <div className="flex items-baseline gap-3">
          <h1 className="text-base font-semibold">岗位管理</h1>
          <span className="text-[11px] tabular-nums text-muted">
            共 {jobsQuery.data?.items.length || 0} 个岗位
          </span>
        </div>
        <Button
          size="sm"
          onClick={() => {
            setError("");
            setOpen(true);
          }}
        >
          <PlusIcon className="h-3.5 w-3.5" /> 发布岗位
        </Button>
      </header>

      {jobsQuery.isLoading && (
        <div className="mt-4 space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      )}

      {jobsQuery.data && jobsQuery.data.items.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="还没有发布岗位"
            description="手动发布一个，或者直接对招聘助手说「帮我招一个 Python 后端」。"
            action={<Button onClick={() => setOpen(true)}>发布第一个岗位</Button>}
          />
        </div>
      )}

      {jobs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-x-8 gap-y-1 border-b border-line pb-3 text-xs">
          <span>
            <span className="mr-1.5 text-muted">在招岗位</span>
            <span className="font-semibold tabular-nums">{openCount}</span>
          </span>
          <span>
            <span className="mr-1.5 text-muted">已关闭</span>
            <span className="font-semibold tabular-nums">{jobs.length - openCount}</span>
          </span>
          <span>
            <span className="mr-1.5 text-muted">累计投递</span>
            <span className="font-semibold tabular-nums">{totalApplicants}</span>
          </span>
        </div>
      )}

      {jobsQuery.data && jobsQuery.data.items.length > 0 && (
        <div className="mt-4 overflow-x-auto border border-line bg-surface">
          <table className="recruiter-table min-w-[680px]">
            <thead>
              <tr>
                <th className="w-[80px]">编号</th>
                <th>岗位</th>
                <th className="w-[70px]">城市</th>
                <th className="w-[100px]">薪资</th>
                <th className="w-[70px] text-right">投递</th>
                <th className="w-[80px]">状态</th>
                <th className="w-[140px] text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {jobsQuery.data.items.map((job) => {
                const meta = STATUS_META[job.status] || STATUS_META.open;
                return (
                  <tr key={job.id}>
                    <td className="text-[11px] tabular-nums text-muted">
                      JOB-{String(job.id).padStart(3, "0")}
                    </td>
                    <td>
                      <p className="font-medium">{job.title}</p>
                      <p className="mt-0.5 text-[11px] text-muted">
                        {job.required_skills.slice(0, 4).join(" · ")}
                      </p>
                    </td>
                    <td className="text-xs text-muted">{job.location}</td>
                    <td className="text-xs tabular-nums">
                      {job.salary_min}-{job.salary_max}K
                    </td>
                    <td className="text-right text-xs tabular-nums">{job.applicant_count}</td>
                    <td>
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                    </td>
                    <td className="whitespace-nowrap text-right">
                      <button
                        onClick={() =>
                          toggleMutation.mutate({
                            id: job.id,
                            status: job.status === "open" ? "closed" : "open",
                          })
                        }
                        className="text-xs text-muted transition-colors hover:text-ink"
                      >
                        {job.status === "open" ? "关闭" : "重新开放"}
                      </button>
                      <Link
                        to={`/employer/board?jobId=${job.id}`}
                        className="ml-3 text-xs font-medium text-primary hover:underline"
                      >
                        候选人 <ArrowRightIcon className="inline h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={open}
        title="发布新岗位"
        width="max-w-2xl"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button loading={createMutation.isPending} onClick={() => createMutation.mutate()}>
              发布岗位
            </Button>
          </>
        }
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <Field label="岗位标题">
              <Input value={form.title} onChange={update("title")} placeholder="如 Python 后端开发工程师" />
            </Field>
          </div>
          <Field label="城市">
            <Input value={form.location} onChange={update("location")} placeholder="如 上海" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="薪资下限（K）">
              <Input value={form.salary_min} onChange={update("salary_min")} />
            </Field>
            <Field label="薪资上限（K）">
              <Input value={form.salary_max} onChange={update("salary_max")} />
            </Field>
          </div>
          <Field label="经验下限（年）">
            <Input value={form.experience_min} onChange={update("experience_min")} />
          </Field>
          <Field label="经验上限（年）">
            <Input value={form.experience_max} onChange={update("experience_max")} />
          </Field>
          <Field label="必需技能" hint="用逗号分隔">
            <Input
              value={form.required_skills}
              onChange={update("required_skills")}
              placeholder="Python, FastAPI, MySQL"
            />
          </Field>
          <Field label="加分技能" hint="用逗号分隔">
            <Input
              value={form.preferred_skills}
              onChange={update("preferred_skills")}
              placeholder="Docker, Kubernetes"
            />
          </Field>
          <div className="md:col-span-2">
            <Field label="岗位描述">
              <Textarea
                value={form.description}
                onChange={update("description")}
                placeholder="职责与要求……"
                className="min-h-[120px]"
              />
            </Field>
          </div>
          {error && (
            <p className="md:col-span-2 rounded-xl border border-danger bg-danger-soft px-3.5 py-2.5 text-xs text-danger">
              {error}
            </p>
          )}
        </div>
      </Modal>
    </div>
  );
}
