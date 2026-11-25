import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { Application, Candidate, InterviewInvite, Offer } from "../lib/types";
import { formatShortDateTime, localInputToUtcIso, toLocalDateInput } from "../lib/format";
import {
  Badge,
  Button,
  Field,
  Input,
  Modal,
  Select,
  Textarea,
  cn,
} from "./ui";

const MODE_OPTIONS = [
  { label: "视频面试", value: "video" },
  { label: "现场面试", value: "onsite" },
  { label: "电话面试", value: "phone" },
];

function inviteTone(status: InterviewInvite["status"]) {
  if (status === "confirmed") return "success" as const;
  if (status === "pending") return "warning" as const;
  if (status === "declined") return "danger" as const;
  return "default" as const;
}

function offerTone(status: Offer["status"]) {
  if (status === "accepted") return "success" as const;
  if (status === "pending") return "warning" as const;
  if (status === "declined" || status === "expired") return "danger" as const;
  return "default" as const;
}

/* ============================== 求职者端 ============================== */

export function SeekerPipeline({ app }: { app: Application }) {
  const queryClient = useQueryClient();
  const [respondTarget, setRespondTarget] = useState<
    | { kind: "invite"; invite: InterviewInvite; action: "confirm" | "decline" }
    | { kind: "offer"; action: "accept" | "decline" }
    | { kind: "onboarding"; action: "confirm" | "abandon" }
    | null
  >(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["applications", "mine"] });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const inviteMutation = useMutation({
    mutationFn: ({ inviteId, action }: { inviteId: number; action: "confirm" | "decline" }) =>
      api.post(`/applications/${app.id}/interview-invites/${inviteId}/respond`, {
        action,
        note,
      }),
    onSuccess: () => {
      setRespondTarget(null);
      setNote("");
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "操作失败"),
  });

  const offerMutation = useMutation({
    mutationFn: ({ action }: { action: "accept" | "decline" }) =>
      api.post(`/applications/${app.id}/offer/respond`, { action, note }),
    onSuccess: () => {
      setRespondTarget(null);
      setNote("");
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "操作失败"),
  });

  const onboardingMutation = useMutation({
    mutationFn: ({ action }: { action: "confirm" | "abandon" }) =>
      api.post(`/applications/${app.id}/onboarding/${action}`, { note }),
    onSuccess: () => {
      setRespondTarget(null);
      setNote("");
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "操作失败"),
  });

  const invites = app.interview_invites || [];
  const offer = app.offer;
  const onboarding = app.onboarding;
  const inOnboarding = ["onboarding", "hired", "abandoned"].includes(app.status);
  if (invites.length === 0 && !offer && !inOnboarding) return null;

  const close = () => {
    setRespondTarget(null);
    setNote("");
    setError("");
  };

  const submit = () => {
    if (!respondTarget) return;
    if (respondTarget.kind === "offer") {
      offerMutation.mutate({ action: respondTarget.action });
    } else if (respondTarget.kind === "onboarding") {
      onboardingMutation.mutate({ action: respondTarget.action });
    } else {
      inviteMutation.mutate({
        inviteId: respondTarget.invite.id,
        action: respondTarget.action,
      });
    }
  };

  const modalTitle = (() => {
    if (!respondTarget) return "";
    if (respondTarget.kind === "invite") {
      return respondTarget.action === "confirm" ? "确认参加面试" : "无法参加面试";
    }
    if (respondTarget.kind === "offer") {
      return respondTarget.action === "accept" ? "接受 Offer" : "拒绝 Offer";
    }
    return respondTarget.action === "confirm" ? "确认入职" : "放弃入职";
  })();

  const modalHint = (() => {
    if (!respondTarget) return "";
    if (respondTarget.kind === "invite") {
      return respondTarget.action === "confirm"
        ? "确认后招聘方会收到通知，请按约定时间参加面试。"
        : "拒绝后招聘方可以重新安排时间，请尽量说明原因。";
    }
    if (respondTarget.kind === "offer") {
      return respondTarget.action === "accept"
        ? "接受后招聘方会收到通知，该投递将进入待入职阶段。"
        : "拒绝后该投递会结束，仍可说明原因方便招聘方了解。";
    }
    return respondTarget.action === "confirm"
      ? "确认后招聘方会收到通知，请按约定日期到岗。"
      : "放弃入职后该投递会结束，招聘方会收到通知。";
  })();

  const modalDanger =
    (respondTarget?.kind === "offer" && respondTarget.action === "decline") ||
    (respondTarget?.kind === "onboarding" && respondTarget.action === "abandon");

  return (
    <div className="mt-3 space-y-2">
      {invites.map((invite) => (
        <div key={invite.id} className="rounded-lg border border-line px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-ink">
                第 {invite.round} 轮面试 · {invite.mode_label}
              </span>
              <Badge tone={inviteTone(invite.status)}>{invite.status_label}</Badge>
            </div>
            {invite.status === "pending" && (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    setError("");
                    setRespondTarget({ kind: "invite", invite, action: "confirm" });
                  }}
                >
                  确认参加
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-danger hover:bg-danger-soft"
                  onClick={() => {
                    setError("");
                    setRespondTarget({ kind: "invite", invite, action: "decline" });
                  }}
                >
                  无法参加
                </Button>
              </div>
            )}
          </div>
          <p className="mt-1 text-[11px] text-muted">
            {formatShortDateTime(invite.scheduled_at)} · 约 {invite.duration_minutes} 分钟
            {invite.location ? ` · ${invite.location}` : ""}
          </p>
          {invite.note && <p className="mt-1 text-[11px] text-muted">说明：{invite.note}</p>}
          {invite.candidate_note && (
            <p className="mt-1 text-[11px] text-muted">我的备注：{invite.candidate_note}</p>
          )}
        </div>
      ))}

      {offer && (
        <div className="rounded-lg border border-line px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-ink">Offer 通知</span>
              <Badge tone={offerTone(offer.status)}>{offer.status_label}</Badge>
            </div>
            {offer.status === "pending" && (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    setError("");
                    setRespondTarget({ kind: "offer", action: "accept" });
                  }}
                >
                  接受 Offer
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-danger hover:bg-danger-soft"
                  onClick={() => {
                    setError("");
                    setRespondTarget({ kind: "offer", action: "decline" });
                  }}
                >
                  拒绝 Offer
                </Button>
              </div>
            )}
          </div>
          <p className="mt-1 text-[11px] text-muted">
            {offer.salary_min}-{offer.salary_max}K
            {offer.start_date ? ` · ${offer.start_date} 入职` : ""}
            {offer.expires_at ? ` · 有效期至 ${formatShortDateTime(offer.expires_at)}` : ""}
          </p>
          {offer.note && <p className="mt-1 text-[11px] text-muted">说明：{offer.note}</p>}
          {offer.response_note && (
            <p className="mt-1 text-[11px] text-muted">我的回复：{offer.response_note}</p>
          )}
        </div>
      )}

      {inOnboarding && (
        <div className="rounded-lg border border-line px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-ink">入职安排</span>
              <Badge
                tone={
                  app.status === "hired"
                    ? "success"
                    : app.status === "abandoned"
                      ? "default"
                      : "primary"
                }
              >
                {app.status_label}
              </Badge>
            </div>
            {app.status === "onboarding" && (
              <div className="flex items-center gap-2">
                {!onboarding.confirmed && (
                  <Button
                    size="sm"
                    onClick={() => {
                      setError("");
                      setRespondTarget({ kind: "onboarding", action: "confirm" });
                    }}
                  >
                    确认入职
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-danger hover:bg-danger-soft"
                  onClick={() => {
                    setError("");
                    setRespondTarget({ kind: "onboarding", action: "abandon" });
                  }}
                >
                  放弃入职
                </Button>
              </div>
            )}
          </div>
          <p className="mt-1 text-[11px] text-muted">
            {onboarding.date ? `${onboarding.date} 入职` : "入职日期待招聘方确认"}
            {" · "}
            {onboarding.confirmed ? "已确认入职安排" : "待确认入职安排"}
            {onboarding.result ? ` · 到岗结果：${onboarding.result_label}` : ""}
          </p>
          {onboarding.note && (
            <p className="mt-1 text-[11px] text-muted">备注：{onboarding.note}</p>
          )}
          <p className="mt-1 text-[11px] text-primary">
            下一步：
            {app.status === "hired"
              ? "已完成入职"
              : app.status === "abandoned"
                ? "已放弃入职，流程结束"
                : onboarding.confirmed
                  ? "等待到岗，招聘方将记录实际结果"
                  : "确认入职安排"}
          </p>
        </div>
      )}

      <Modal
        open={respondTarget !== null}
        title={modalTitle}
        onClose={close}
        footer={
          <>
            <Button variant="ghost" onClick={close}>
              取消
            </Button>
            <Button
              variant={modalDanger ? "danger" : "primary"}
              loading={
                inviteMutation.isPending ||
                offerMutation.isPending ||
                onboardingMutation.isPending
              }
              onClick={submit}
            >
              确认提交
            </Button>
          </>
        }
      >
        <p className="text-xs leading-relaxed text-muted">{modalHint}</p>
        <div className="mt-4">
          <Field label="备注（选填）">
            <Textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="如有时间冲突或其他情况，可以补充说明"
            />
          </Field>
        </div>
        {error && (
          <p className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
            {error}
          </p>
        )}
      </Modal>
    </div>
  );
}

/* ============================== 招聘方端 ============================== */

export function EmployerPipeline({
  candidate,
  jobId,
}: {
  candidate: Candidate;
  jobId: number | "all";
}) {
  const queryClient = useQueryClient();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [offerOpen, setOfferOpen] = useState(false);
  const [onboardingTarget, setOnboardingTarget] = useState<
    "hired" | "abandoned" | null
  >(null);
  const [onboardingNote, setOnboardingNote] = useState("");
  const [onboardingDate, setOnboardingDate] = useState("");
  const [cancelTarget, setCancelTarget] = useState<InterviewInvite | null>(null);
  const [cancelNote, setCancelNote] = useState("");
  const [error, setError] = useState("");
  const [inviteForm, setInviteForm] = useState({
    scheduled_at: "",
    duration_minutes: "45",
    mode: "video",
    location: "",
    note: "",
  });
  const [offerForm, setOfferForm] = useState({
    salary_min: "",
    salary_max: "",
    start_date: "",
    expires_date: "",
    note: "",
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["candidates", jobId] });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const inviteMutation = useMutation({
    mutationFn: () =>
      api.post(`/applications/${candidate.application_id}/interview-invites`, {
        scheduled_at: localInputToUtcIso(inviteForm.scheduled_at),
        duration_minutes: Number(inviteForm.duration_minutes) || 45,
        mode: inviteForm.mode,
        location: inviteForm.location.trim(),
        note: inviteForm.note.trim(),
      }),
    onSuccess: () => {
      setInviteOpen(false);
      setInviteForm({ scheduled_at: "", duration_minutes: "45", mode: "video", location: "", note: "" });
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "发送邀约失败"),
  });

  const cancelMutation = useMutation({
    mutationFn: (invite: InterviewInvite) =>
      api.post(
        `/applications/${candidate.application_id}/interview-invites/${invite.id}/cancel`,
        { note: cancelNote.trim() },
      ),
    onSuccess: () => {
      setCancelTarget(null);
      setCancelNote("");
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "取消失败"),
  });

  const completeMutation = useMutation({
    mutationFn: (invite: InterviewInvite) =>
      api.post(
        `/applications/${candidate.application_id}/interview-invites/${invite.id}/complete`,
        { note: "" },
      ),
    onSuccess: () => {
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "标记完成失败"),
  });

  const offerMutation = useMutation({
    mutationFn: () =>
      api.post(`/applications/${candidate.application_id}/offer`, {
        salary_min: Number(offerForm.salary_min) || 0,
        salary_max: Number(offerForm.salary_max) || 0,
        start_date: offerForm.start_date,
        expires_at: offerForm.expires_date
          ? localInputToUtcIso(`${offerForm.expires_date}T23:59:59`)
          : null,
        note: offerForm.note.trim(),
      }),
    onSuccess: () => {
      setOfferOpen(false);
      setError("");
      invalidate();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "发送 Offer 失败"),
  });

  const onboardingMutation = useMutation({
    mutationFn: () =>
      api.post(`/applications/${candidate.application_id}/onboarding/result`, {
        result: onboardingTarget,
        note: onboardingNote.trim(),
        onboarding_date: onboardingDate,
      }),
    onSuccess: () => {
      setOnboardingTarget(null);
      setOnboardingNote("");
      setOnboardingDate("");
      setError("");
      invalidate();
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "记录入职结果失败"),
  });

  const invites = candidate.interview_invites || [];
  const offer = candidate.offer;
  const onboarding = candidate.onboarding;
  const inOnboarding = ["onboarding", "hired", "abandoned"].includes(
    candidate.status,
  );

  const openOnboarding = (result: "hired" | "abandoned") => {
    setError("");
    setOnboardingTarget(result);
    setOnboardingNote("");
    setOnboardingDate(onboarding.date || "");
  };

  const openOfferForm = (current?: Offer) => {
    setError("");
    setOfferForm(
      current
        ? {
            salary_min: String(current.salary_min),
            salary_max: String(current.salary_max),
            start_date: current.start_date || "",
            expires_date: toLocalDateInput(current.expires_at),
            note: current.note || "",
          }
        : { salary_min: "", salary_max: "", start_date: "", expires_date: "", note: "" },
    );
    setOfferOpen(true);
  };

  return (
    <div className="border-t border-line pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold text-ink">面试与 Offer</p>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="soft"
            onClick={() => {
              setError("");
              setInviteOpen(true);
            }}
            disabled={
              candidate.status === "rejected" ||
              candidate.status === "offer" ||
              inOnboarding
            }
          >
            安排面试
          </Button>
          {!offer && !inOnboarding && (
            <Button
              size="sm"
              onClick={() => openOfferForm()}
              disabled={candidate.status === "rejected"}
            >
              发起 Offer
            </Button>
          )}
        </div>
      </div>

      {invites.length === 0 && !offer && (
        <p className="mt-2 text-[11px] text-muted">还没有面试邀约或 Offer。</p>
      )}

      <div className="mt-2 space-y-2">
        {invites.map((invite) => (
          <div key={invite.id} className="rounded-lg border border-line px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-ink">
                  第 {invite.round} 轮 · {formatShortDateTime(invite.scheduled_at)}
                </span>
                <Badge tone={inviteTone(invite.status)}>{invite.status_label}</Badge>
              </div>
              {(invite.status === "pending" || invite.status === "confirmed") && (
                <div className="flex items-center gap-2">
                  <button
                    className="text-[11px] text-primary hover:underline"
                    disabled={completeMutation.isPending}
                    onClick={() => completeMutation.mutate(invite)}
                  >
                    标记完成
                  </button>
                  <button
                    className={cn("text-[11px] text-danger hover:underline")}
                    onClick={() => {
                      setError("");
                      setCancelTarget(invite);
                    }}
                  >
                    取消邀约
                  </button>
                </div>
              )}
            </div>
            <p className="mt-0.5 text-[11px] text-muted">
              {invite.mode_label} · 约 {invite.duration_minutes} 分钟
              {invite.location ? ` · ${invite.location}` : ""}
            </p>
            {invite.candidate_note && (
              <p className="mt-0.5 text-[11px] text-muted">候选人备注：{invite.candidate_note}</p>
            )}
          </div>
        ))}

        {offer && (
          <div className="rounded-lg border border-line px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-medium text-ink">Offer</span>
              <div className="flex items-center gap-2">
                <Badge tone={offerTone(offer.status)}>{offer.status_label}</Badge>
                {offer.status === "pending" && (
                  <button
                    className="text-[11px] text-primary hover:underline"
                    onClick={() => openOfferForm(offer)}
                  >
                    修改
                  </button>
                )}
              </div>
            </div>
            <p className="mt-0.5 text-[11px] text-muted">
              {offer.salary_min}-{offer.salary_max}K
              {offer.start_date ? ` · ${offer.start_date} 入职` : ""}
              {offer.expires_at ? ` · 有效期至 ${formatShortDateTime(offer.expires_at)}` : ""}
            </p>
            {offer.note && <p className="mt-0.5 text-[11px] text-muted">说明：{offer.note}</p>}
            {offer.response_note && (
              <p className="mt-0.5 text-[11px] text-muted">候选人备注：{offer.response_note}</p>
            )}
          </div>
        )}

        {inOnboarding && (
          <div className="rounded-lg border border-line px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-ink">入职安排</span>
                <Badge
                  tone={
                    candidate.status === "hired"
                      ? "success"
                      : candidate.status === "abandoned"
                        ? "default"
                        : "primary"
                  }
                >
                  {candidate.status_label}
                </Badge>
              </div>
              {candidate.status === "onboarding" && (
                <div className="flex items-center gap-2">
                  <Button size="sm" onClick={() => openOnboarding("hired")}>
                    记录已入职
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-danger hover:bg-danger-soft"
                    onClick={() => openOnboarding("abandoned")}
                  >
                    记录放弃入职
                  </Button>
                </div>
              )}
            </div>
            <p className="mt-0.5 text-[11px] text-muted">
              {onboarding.date ? `${onboarding.date} 入职` : "入职日期待定"}
              {" · "}
              {onboarding.confirmed ? "候选人已确认" : "候选人待确认"}
              {onboarding.result ? ` · 到岗结果：${onboarding.result_label}` : ""}
            </p>
            {onboarding.note && (
              <p className="mt-0.5 text-[11px] text-muted">备注：{onboarding.note}</p>
            )}
            <p className="mt-0.5 text-[11px] text-primary">
              下一步：
              {candidate.status === "hired"
                ? "已完成入职"
                : candidate.status === "abandoned"
                  ? "已放弃入职，流程结束"
                  : onboarding.confirmed
                    ? "记录实际到岗结果"
                    : "等待候选人确认入职"}
            </p>
          </div>
        )}
      </div>

      {error && !inviteOpen && !offerOpen && !cancelTarget && !onboardingTarget && (
        <p className="mt-2 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
          {error}
        </p>
      )}

      <Modal
        open={inviteOpen}
        title="安排面试"
        onClose={() => setInviteOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setInviteOpen(false)}>
              取消
            </Button>
            <Button
              loading={inviteMutation.isPending}
              disabled={!inviteForm.scheduled_at}
              onClick={() => inviteMutation.mutate()}
            >
              发送邀约
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Field label="面试时间">
            <Input
              type="datetime-local"
              value={inviteForm.scheduled_at}
              onChange={(event) => setInviteForm({ ...inviteForm, scheduled_at: event.target.value })}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="时长（分钟）">
              <Input
                value={inviteForm.duration_minutes}
                onChange={(event) =>
                  setInviteForm({ ...inviteForm, duration_minutes: event.target.value })
                }
                placeholder="45"
              />
            </Field>
            <Field label="面试方式">
              <Select
                ariaLabel="面试方式"
                value={inviteForm.mode}
                onChange={(mode) => setInviteForm({ ...inviteForm, mode })}
                options={MODE_OPTIONS}
              />
            </Field>
          </div>
          <Field label="地点 / 会议链接">
            <Input
              value={inviteForm.location}
              onChange={(event) => setInviteForm({ ...inviteForm, location: event.target.value })}
              placeholder="如 会议室 A / 腾讯会议链接"
            />
          </Field>
          <Field label="补充说明（选填）">
            <Textarea
              value={inviteForm.note}
              onChange={(event) => setInviteForm({ ...inviteForm, note: event.target.value })}
              placeholder="面试官、需要准备的材料等"
            />
          </Field>
          {error && (
            <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
              {error}
            </p>
          )}
        </div>
      </Modal>

      <Modal
        open={offerOpen}
        title={offer?.status === "pending" ? "修改 Offer" : "发起 Offer"}
        onClose={() => setOfferOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOfferOpen(false)}>
              取消
            </Button>
            <Button loading={offerMutation.isPending} onClick={() => offerMutation.mutate()}>
              {offer?.status === "pending" ? "保存修改" : "发送 Offer"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="最低月薪（K）">
              <Input
                value={offerForm.salary_min}
                onChange={(event) => setOfferForm({ ...offerForm, salary_min: event.target.value })}
                placeholder="如 30"
              />
            </Field>
            <Field label="最高月薪（K）">
              <Input
                value={offerForm.salary_max}
                onChange={(event) => setOfferForm({ ...offerForm, salary_max: event.target.value })}
                placeholder="如 40"
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="入职日期">
              <Input
                type="date"
                value={offerForm.start_date}
                onChange={(event) => setOfferForm({ ...offerForm, start_date: event.target.value })}
              />
            </Field>
            <Field label="有效期至">
              <Input
                type="date"
                value={offerForm.expires_date}
                onChange={(event) =>
                  setOfferForm({ ...offerForm, expires_date: event.target.value })
                }
              />
            </Field>
          </div>
          <Field label="Offer 说明（选填）">
            <Textarea
              value={offerForm.note}
              onChange={(event) => setOfferForm({ ...offerForm, note: event.target.value })}
              placeholder="岗位、汇报对象、福利等补充信息"
            />
          </Field>
          {error && (
            <p className="rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
              {error}
            </p>
          )}
        </div>
      </Modal>

      <Modal
        open={onboardingTarget !== null}
        title={onboardingTarget === "hired" ? "记录已入职" : "记录放弃入职"}
        onClose={() => setOnboardingTarget(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOnboardingTarget(null)}>
              取消
            </Button>
            <Button
              variant={onboardingTarget === "abandoned" ? "danger" : "primary"}
              loading={onboardingMutation.isPending}
              onClick={() => onboardingMutation.mutate()}
            >
              确认记录
            </Button>
          </>
        }
      >
        <p className="text-xs leading-relaxed text-muted">
          {onboardingTarget === "hired"
            ? "记录后投递将标记为已入职，候选人会收到站内通知。"
            : "记录后投递将标记为放弃入职，候选人会收到站内通知。"}
        </p>
        <div className="mt-4 space-y-3">
          <Field label="入职日期">
            <Input
              type="date"
              value={onboardingDate}
              onChange={(event) => setOnboardingDate(event.target.value)}
            />
          </Field>
          <Field label="备注（选填）">
            <Textarea
              value={onboardingNote}
              onChange={(event) => setOnboardingNote(event.target.value)}
              placeholder="如：已按期到岗 / 候选人临时决定放弃"
            />
          </Field>
        </div>
        {error && (
          <p className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-[11px] text-danger">
            {error}
          </p>
        )}
      </Modal>

      <Modal
        open={cancelTarget !== null}
        title="取消面试邀约"
        onClose={() => setCancelTarget(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancelTarget(null)}>
              返回
            </Button>
            <Button
              variant="danger"
              loading={cancelMutation.isPending}
              onClick={() => cancelTarget && cancelMutation.mutate(cancelTarget)}
            >
              确认取消
            </Button>
          </>
        }
      >
        <p className="text-xs leading-relaxed text-muted">
          取消后候选人会收到通知，可稍后重新安排新的面试时间。
        </p>
        <div className="mt-4">
          <Field label="取消原因（选填）">
            <Textarea
              value={cancelNote}
              onChange={(event) => setCancelNote(event.target.value)}
              placeholder="如 面试官临时有安排"
            />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
