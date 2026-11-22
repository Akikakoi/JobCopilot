import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api, fetchBlob } from "../lib/api";
import type { Job, Resume, ResumeOptimize, ResumeVersion } from "../lib/types";
import { formatDateTime } from "../lib/format";
import { CheckIcon, UploadIcon } from "../components/icons";
import { JobPicker } from "../components/JobPicker";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Modal,
  Skeleton,
  Textarea,
  cn,
} from "../components/ui";

const STEPS = ["读取文本", "抽取信息", "更新档案"];

function ParsingOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <Card className="w-[320px] p-6">
        <p className="text-sm font-semibold">正在解析简历</p>
        <p className="mt-1 text-xs text-muted">通常需要 5-15 秒，请稍候</p>
        <div className="mt-5 space-y-3">
          {STEPS.map((step, index) => (
            <div key={step} className="flex items-center gap-3 text-xs">
              <span
                className="flex h-5 w-5 items-center justify-center rounded-full bg-primary-soft text-[10px] font-semibold text-primary"
                style={{ animation: "pulse-soft 1.4s ease-in-out infinite", animationDelay: `${index * 160}ms` }}
              >
                {index + 1}
              </span>
              <span className="text-muted">{step}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function StructuredView({
  resume,
  onPreview,
  onDownload,
  fileBusy,
}: {
  resume: Resume;
  onPreview: () => void;
  onDownload: () => void;
  fileBusy: boolean;
}) {
  const s = resume.structured;
  const exp = s.expectations || { locations: [], job_types: [] };

  return (
    <div className="space-y-4 animate-fade-up">
      <Card className="overflow-hidden">
        <div className="border-b border-line px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-semibold tracking-tight">{s.name || "未识别姓名"}</h2>
                <Badge tone="success">
                  <CheckIcon className="mr-1 h-3 w-3" /> 已结构化
                </Badge>
              </div>
              <p className="mt-1 text-sm text-muted">
                {s.title || "未填写目标职位"} · {s.years_of_experience} 年经验
              </p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className="space-y-1 text-right text-xs text-muted">
                <p>期望城市：{exp.locations?.join("、") || "未填写"}</p>
                <p>
                  期望薪资：
                  {exp.salary_min || exp.salary_max ? `${exp.salary_min ?? "?"}-${exp.salary_max ?? "?"}K` : "未填写"}
                </p>
                <p>简历来源：{resume.source === "upload" ? "文件上传" : "文本粘贴"}</p>
                {resume.file && <p>原文件：{resume.file.name}</p>}
              </div>
              {resume.file && (
                <div className="flex gap-2">
                  {resume.file.previewable && (
                    <Button size="sm" variant="soft" loading={fileBusy} onClick={onPreview}>
                      预览原文件
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" disabled={fileBusy} onClick={onDownload}>
                    下载原文件
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="px-6 py-5">
          <p className="text-[11px] font-semibold text-muted">技能标签</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(s.skills || []).length ? (
              s.skills.map((skill) => (
                <span key={skill} className="chip chip-primary">
                  {skill}
                </span>
              ))
            ) : (
              <span className="text-xs text-muted">未识别到技能</span>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="p-5">
          <p className="text-[11px] font-semibold text-muted">教育经历</p>
          <div className="mt-3 space-y-3">
            {(s.education || []).length ? (
              s.education.map((edu, index) => (
                <div key={`${edu.school}-${index}`} className="border-l-2 border-line pl-3">
                  <p className="text-sm font-medium">{edu.school}</p>
                  <p className="text-xs text-muted">
                    {edu.major} · {edu.degree}
                  </p>
                  <p className="text-[11px] text-muted">{edu.period}</p>
                </div>
              ))
            ) : (
              <p className="text-xs text-muted">未识别</p>
            )}
          </div>
        </Card>

        <Card className="p-5">
          <p className="text-[11px] font-semibold text-muted">工作经历</p>
          <div className="mt-3 space-y-4">
            {(s.work_experience || []).length ? (
              s.work_experience.map((work, index) => (
                <div key={`${work.company}-${index}`} className="border-l-2 border-line pl-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="text-sm font-medium">{work.company}</p>
                    <span className="shrink-0 text-[11px] text-muted">{work.period}</span>
                  </div>
                  <p className="text-xs text-muted">{work.role}</p>
                  {work.highlights.length > 0 && (
                    <ul className="mt-1.5 space-y-1">
                      {work.highlights.map((item) => (
                        <li key={item} className="text-xs leading-relaxed text-muted">
                          · {item}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs text-muted">未识别</p>
            )}
          </div>
        </Card>
      </div>

      <details className="group rounded-2xl border border-line bg-surface px-5 py-3">
        <summary className="cursor-pointer list-none text-xs font-medium text-muted transition-colors hover:text-ink">
          查看简历原文（{resume.raw_text.length} 字）
        </summary>
        <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-neutral-soft p-4 text-[11px] leading-relaxed text-muted">
          {resume.raw_text}
        </pre>
      </details>
    </div>
  );
}

export function ResumePage() {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"upload" | "paste">("upload");
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [optJob, setOptJob] = useState("");
  const [optimizeError, setOptimizeError] = useState("");
  const [optimizeResult, setOptimizeResult] = useState<ResumeOptimize | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [pendingRestore, setPendingRestore] = useState<ResumeVersion | null>(null);
  const [fileBusy, setFileBusy] = useState(false);

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  const resumeQuery = useQuery({
    queryKey: ["resume", "mine"],
    queryFn: () => api.get<Resume | null>("/resumes/mine"),
  });

  const versionsQuery = useQuery({
    queryKey: ["resume-versions"],
    queryFn: () => api.get<{ items: ResumeVersion[] }>("/resumes/versions"),
  });

  const jobsQuery = useQuery({
    queryKey: ["jobs", "resume-optimize"],
    queryFn: () => api.get<{ items: Job[] }>("/jobs"),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["resume", "mine"] });
    queryClient.invalidateQueries({ queryKey: ["resume-versions"] });
    queryClient.invalidateQueries({ queryKey: ["match-jobs"] });
    queryClient.invalidateQueries({ queryKey: ["match-detail"] });
  };

  const loadFileUrl = async () => URL.createObjectURL(await fetchBlob("/resumes/mine/file"));

  const handlePreview = async () => {
    setError("");
    setFileBusy(true);
    try {
      setPreviewUrl(await loadFileUrl());
      setPreviewOpen(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "简历原文件加载失败");
    } finally {
      setFileBusy(false);
    }
  };

  const handleDownload = async () => {
    setError("");
    setFileBusy(true);
    try {
      const url = await loadFileUrl();
      const link = document.createElement("a");
      link.href = url;
      link.download = resumeQuery.data?.file?.name || "resume";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "简历原文件下载失败");
    } finally {
      setFileBusy(false);
    }
  };

  const optimizeMutation = useMutation({
    mutationFn: (jobId: number) => api.post<ResumeOptimize>("/resumes/optimize", { job_id: jobId }),
    onSuccess: (data) => {
      setOptimizeError("");
      setOptimizeResult(data);
    },
    onError: (err) => {
      setOptimizeResult(null);
      setOptimizeError(err instanceof ApiError ? err.message : "生成优化建议失败");
    },
  });

  const applyMutation = useMutation({
    mutationFn: () =>
      api.post<Resume>("/resumes/optimize/apply", {
        job_id: Number(optJob),
        skills_to_add: optimizeResult?.skills_to_add || [],
      }),
    onSuccess: (data) => {
      setOptimizeResult(null);
      setOptimizeError("");
      setNotice("已应用优化并生成新版本");
      queryClient.setQueryData(["resume", "mine"], data);
      invalidate();
    },
    onError: (err) => setOptimizeError(err instanceof ApiError ? err.message : "应用优化失败"),
  });

  const restoreMutation = useMutation({
    mutationFn: (versionId: number) =>
      api.post<Resume>(`/resumes/versions/${versionId}/restore`),
    onSuccess: (data) => {
      setPendingRestore(null);
      setNotice("已回滚到所选版本");
      queryClient.setQueryData(["resume", "mine"], data);
      invalidate();
    },
    onError: (err) => {
      setPendingRestore(null);
      setError(err instanceof ApiError ? err.message : "回滚失败");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<Resume>("/resumes/upload", form);
    },
    onSuccess: () => {
      setError("");
      setNotice("简历解析完成，向量已更新");
      invalidate();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "解析失败，请重试");
    },
  });

  const pasteMutation = useMutation({
    mutationFn: () => api.post<Resume>("/resumes/paste", { text }),
    onSuccess: () => {
      setError("");
      setNotice("简历解析完成，向量已更新");
      setText("");
      invalidate();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "解析失败，请重试");
    },
  });

  const reparseMutation = useMutation({
    mutationFn: () => api.put<Resume>("/resumes/mine", {}),
    onSuccess: () => {
      setNotice("重新解析完成");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "重新解析失败"),
  });

  const busy = uploadMutation.isPending || pasteMutation.isPending || reparseMutation.isPending;

  const handleFile = (file: File | undefined) => {
    if (!file) return;
    setError("");
    setNotice("");
    uploadMutation.mutate(file);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      {busy && <ParsingOverlay />}

      <header className="animate-fade-up">
        <h1 className="text-[26px] font-semibold tracking-tight">我的简历</h1>
      </header>

      {error && (
        <div className="mt-5 rounded-xl border border-danger bg-danger-soft px-4 py-3 text-xs text-danger">
          {error}
        </div>
      )}
      {notice && (
        <div className="mt-5 rounded-xl border border-success bg-success-soft px-4 py-3 text-xs text-success">
          {notice}
        </div>
      )}

      <div className="mt-6 grid gap-5 lg:grid-cols-[380px_1fr]">
        <div className="h-fit space-y-4">
        <Card className="p-5">
          <div className="flex items-center gap-1 rounded-xl border border-line bg-neutral-soft p-1">
            {(
              [
                ["upload", "上传文件"],
                ["paste", "粘贴文本"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setTab(value)}
                className={cn(
                  "flex-1 rounded-lg py-2 text-xs font-medium transition-colors",
                  tab === value ? "bg-surface font-semibold text-ink" : "text-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "upload" ? (
            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                handleFile(event.dataTransfer.files?.[0]);
              }}
              onClick={() => fileRef.current?.click()}
              className={cn(
                "mt-4 flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-line bg-neutral-soft px-5 py-10 text-center transition-colors",
                dragging && "border-primary bg-surface",
              )}
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-line bg-surface text-primary">
                <UploadIcon className="h-5 w-5" />
              </div>
              <p className="mt-3 text-sm font-medium">拖拽简历到这里，或点击选择</p>
              <p className="mt-1 text-[11px] text-muted">支持 PDF / DOCX / TXT / MD，单文件不超过 5MB</p>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.txt,.md"
                className="hidden"
                onChange={(event) => handleFile(event.target.files?.[0] ?? undefined)}
              />
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="把简历全文粘贴到这里，至少 20 个字符……"
                className="min-h-[240px] text-xs leading-relaxed"
              />
              <Button
                className="w-full"
                loading={pasteMutation.isPending}
                disabled={text.trim().length < 20}
                onClick={() => pasteMutation.mutate()}
              >
                解析文本
              </Button>
            </div>
          )}

          <div className="mt-4 border-l-2 border-line pl-3 text-[11px] leading-relaxed text-muted">
            解析失败的常见原因：扫描版 PDF、双栏排版、非简历内容。可改用文本粘贴。
          </div>

          {resumeQuery.data && (
            <Button
              variant="ghost"
              className="mt-3 w-full"
              loading={reparseMutation.isPending}
              onClick={() => reparseMutation.mutate()}
            >
              用原文重新解析
            </Button>
          )}
        </Card>

          <Card className="p-4">
            <div className="flex items-center justify-between px-1">
              <p className="text-[11px] font-semibold text-muted">版本历史</p>
              <span className="text-[10px] tabular-nums text-muted">
                {versionsQuery.data?.items.length || 0}
              </span>
            </div>
            <div className="mt-2 max-h-64 space-y-1.5 overflow-y-auto">
              {versionsQuery.data?.items.map((version) => (
                <div
                  key={version.id}
                  className="flex items-center justify-between gap-2 border-b border-line px-1 py-2 last:border-b-0"
                >
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium">{version.label}</p>
                    <p className="truncate text-[10px] text-muted">
                      {version.note || version.title} ·{" "}
                      {formatDateTime(version.created_at)}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={restoreMutation.isPending}
                    onClick={() => setPendingRestore(version)}
                  >
                    回滚
                  </Button>
                </div>
              ))}
              {!versionsQuery.isLoading && !versionsQuery.data?.items.length && (
                <p className="px-1 py-4 text-center text-[11px] text-muted">
                  暂无历史版本，上传或优化后会生成快照
                </p>
              )}
            </div>
          </Card>
        </div>

        <div>
          {resumeQuery.isLoading && (
            <div className="space-y-4">
              <Skeleton className="h-48 w-full" />
              <div className="grid gap-4 md:grid-cols-2">
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            </div>
          )}

          {!resumeQuery.isLoading && !resumeQuery.data && (
            <EmptyState
              title="还没有简历"
              description="左侧上传或粘贴一份简历，AI 会抽取技能、经历与期望，用于计算岗位匹配度。"
            />
          )}

          {resumeQuery.data && (
            <div className="space-y-4">
              <Card className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-[11px] font-semibold text-muted">
                      按岗位优化
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted">
                      针对目标岗位给出缺失技能与改写建议，应用后生成新版本
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <JobPicker
                      className="w-[240px]"
                      ariaLabel="目标岗位"
                      value={optJob}
                      onChange={setOptJob}
                      jobs={jobsQuery.data?.items || []}
                      placeholder="选择目标岗位"
                    />
                    <Button
                      size="sm"
                      loading={optimizeMutation.isPending}
                      disabled={!optJob}
                      onClick={() => {
                        setOptimizeError("");
                        optimizeMutation.mutate(Number(optJob));
                      }}
                    >
                      生成建议
                    </Button>
                  </div>
                </div>

                {optimizeError && (
                  <p className="mt-3 rounded-xl border border-danger bg-danger-soft px-3 py-2 text-xs text-danger">
                    {optimizeError}
                  </p>
                )}

                {optimizeResult && (
                  <div className="mt-4 space-y-3">
                    <p className="text-xs leading-relaxed text-muted">{optimizeResult.summary}</p>

                    {optimizeResult.missing_skills.length > 0 && (
                      <div>
                        <p className="text-[11px] font-semibold text-warning">缺失技能</p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {optimizeResult.missing_skills.map((skill) => (
                            <span key={skill} className="chip chip-warning">
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {optimizeResult.rewrites.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[11px] font-semibold text-primary">表达改写</p>
                        {optimizeResult.rewrites.map((rewrite, index) => (
                          <div key={index} className="border-l-2 border-line pl-3">
                            <p className="text-[10px] text-muted">{rewrite.target}</p>
                            {rewrite.original && (
                              <p className="mt-1 text-[11px] text-muted line-through">
                                {rewrite.original}
                              </p>
                            )}
                            <p className="mt-1 text-xs leading-relaxed text-ink">
                              {rewrite.suggestion}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {optimizeResult.suggestions.length > 0 && (
                      <ul className="space-y-1.5">
                        {optimizeResult.suggestions.map((item) => (
                          <li key={item} className="flex gap-2 text-xs leading-relaxed text-muted">
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" />
                            {item}
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
                      <p className="text-[11px] text-muted">
                        应用会补充 {optimizeResult.skills_to_add.length} 个技能并生成新版本
                      </p>
                      <Button
                        size="sm"
                        loading={applyMutation.isPending}
                        disabled={optimizeResult.skills_to_add.length === 0}
                        onClick={() => applyMutation.mutate()}
                      >
                        应用技能补充
                      </Button>
                    </div>
                  </div>
                )}
              </Card>

              <StructuredView
                resume={resumeQuery.data}
                onPreview={handlePreview}
                onDownload={handleDownload}
                fileBusy={fileBusy}
              />
            </div>
          )}
        </div>
      </div>

      <Modal
        open={previewOpen}
        title={resumeQuery.data?.file?.name || "简历原文件"}
        onClose={() => setPreviewOpen(false)}
        width="max-w-4xl"
      >
        {previewUrl ? (
          <iframe
            src={previewUrl}
            title="简历原文件预览"
            className="h-[60vh] w-full rounded-lg border border-line bg-neutral-soft"
          />
        ) : (
          <p className="text-xs text-muted">正在加载…</p>
        )}
      </Modal>

      <Modal
        open={pendingRestore !== null}
        title="回滚简历版本"
        onClose={() => setPendingRestore(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingRestore(null)}>
              取消
            </Button>
            <Button
              loading={restoreMutation.isPending}
              onClick={() => pendingRestore && restoreMutation.mutate(pendingRestore.id)}
            >
              确认回滚
            </Button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-ink">
          确定回滚到「{pendingRestore?.label}」？
        </p>
        <p className="mt-2 text-xs leading-relaxed text-muted">
          当前简历内容会先保存为一个新的版本快照，回滚后不会丢失。
        </p>
      </Modal>
    </div>
  );
}
