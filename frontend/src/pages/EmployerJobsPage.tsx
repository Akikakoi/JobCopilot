import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { Job } from "../lib/types";
import { ArrowRightIcon, PlusIcon } from "../components/icons";
import {
  Badge,
  Button,
  Card,
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

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <header className="flex flex-wrap items-end justify-between gap-3 animate-fade-up">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-primary">Job Management</p>
          <h1 className="mt-1.5 text-[26px] font-semibold tracking-tight">岗位管理</h1>
          <p className="mt-1 text-sm text-muted">发布、维护岗位，查看每个岗位的候选人。</p>
        </div>
        <Button
          onClick={() => {
            setError("");
            setOpen(true);
          }}
        >
          <PlusIcon className="h-4 w-4" /> 发布岗位
        </Button>
      </header>

      {jobsQuery.isLoading && (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full" />
          ))}
        </div>
      )}

      {jobsQuery.data && jobsQuery.data.items.length === 0 && (
        <div className="mt-8">
          <EmptyState
            title="还没有发布岗位"
            description="手动发布一个，或者直接对招聘助手说「帮我招一个 Python 后端」。"
            action={<Button onClick={() => setOpen(true)}>发布第一个岗位</Button>}
          />
        </div>
      )}

      <div className="mt-6 space-y-3 stagger">
        {jobsQuery.data?.items.map((job) => {
          const meta = STATUS_META[job.status] || STATUS_META.open;
          return (
            <Card key={job.id} className="p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-[15px] font-semibold">{job.title}</h3>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    <span className="text-xs text-muted">
                      收到 <span className="font-semibold text-primary">{job.applicant_count}</span> 份投递
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {job.location} · {job.experience_min}-{job.experience_max} 年 · {job.salary_min}-
                    {job.salary_max}K
                  </p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {job.required_skills.slice(0, 6).map((skill) => (
                      <span key={skill} className="chip">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      toggleMutation.mutate({
                        id: job.id,
                        status: job.status === "open" ? "closed" : "open",
                      })
                    }
                  >
                    {job.status === "open" ? "关闭岗位" : "重新开放"}
                  </Button>
                  <Link to={`/employer/board?jobId=${job.id}`}>
                    <Button size="sm">
                      候选人看板 <ArrowRightIcon className="h-3.5 w-3.5" />
                    </Button>
                  </Link>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

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
            <p className="md:col-span-2 rounded-xl bg-[#FDECEC] px-3.5 py-2.5 text-xs text-danger">
              {error}
            </p>
          )}
        </div>
      </Modal>
    </div>
  );
}
