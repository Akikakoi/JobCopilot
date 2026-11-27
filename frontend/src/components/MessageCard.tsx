import { useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../lib/api";
import type { ChatMessage, InterviewInvite, Offer } from "../lib/types";
import { formatDateTime } from "../lib/format";
import { Badge, Button } from "./ui";

type Tone = "default" | "primary" | "success" | "warning" | "danger";

const INVITE_TONES: Record<InterviewInvite["status"], Tone> = {
  pending: "warning",
  confirmed: "success",
  declined: "danger",
  cancelled: "default",
  completed: "success",
};

const OFFER_TONES: Record<Offer["status"], Tone> = {
  pending: "warning",
  accepted: "success",
  declined: "danger",
  expired: "default",
  withdrawn: "default",
};

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-14 shrink-0 text-muted">{label}</span>
      <span className="min-w-0 flex-1 break-words text-ink">{children}</span>
    </div>
  );
}

export function MessageCard({
  message,
  role,
}: {
  message: ChatMessage;
  role: "seeker" | "employer";
}) {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");

  const invite =
    message.kind === "interview_invite"
      ? (message.card as InterviewInvite | null)
      : null;
  const offer = message.kind === "offer" ? (message.card as Offer | null) : null;

  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) =>
      api.post(path, body ?? {}),
    onSuccess: () => {
      setError("");
      queryClient.invalidateQueries({ queryKey: ["messages", message.conversation_id] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "操作失败，请重试"),
  });

  const card = invite ?? offer;
  if (!card) return null;

  const base = `/applications/${card.application_id}`;
  const pending = act.isPending;

  const actions: Array<{
    label: string;
    variant?: "soft" | "ghost";
    run: () => void;
  }> = [];

  if (invite) {
    if (role === "seeker" && invite.status === "pending") {
      actions.push({
        label: "确认参加",
        run: () =>
          act.mutate({
            path: `${base}/interview-invites/${invite.id}/respond`,
            body: { action: "confirm" },
          }),
      });
      actions.push({
        label: "无法参加",
        variant: "ghost",
        run: () =>
          act.mutate({
            path: `${base}/interview-invites/${invite.id}/respond`,
            body: { action: "decline" },
          }),
      });
    }
    if (role === "employer" && (invite.status === "pending" || invite.status === "confirmed")) {
      actions.push({
        label: "标记完成",
        variant: "soft",
        run: () =>
          act.mutate({ path: `${base}/interview-invites/${invite.id}/complete` }),
      });
      actions.push({
        label: "取消邀约",
        variant: "ghost",
        run: () =>
          act.mutate({ path: `${base}/interview-invites/${invite.id}/cancel` }),
      });
    }
  }

  if (offer && role === "seeker" && offer.status === "pending") {
    actions.push({
      label: "接受 Offer",
      run: () =>
        act.mutate({
          path: `${base}/offer/respond`,
          body: { action: "accept" },
        }),
    });
    actions.push({
      label: "拒绝",
      variant: "ghost",
      run: () =>
        act.mutate({
          path: `${base}/offer/respond`,
          body: { action: "decline" },
        }),
    });
  }

  return (
    <div className={`flex ${message.mine ? "justify-end" : "justify-start"}`}>
      <div className="w-full max-w-[78%] overflow-hidden rounded-xl border border-line bg-surface">
        <div className="flex items-center justify-between gap-2 border-b border-line bg-primary-soft px-3 py-2">
          <span className="text-[11px] font-semibold text-ink">
            {invite ? `面试邀约 · 第 ${invite.round} 轮` : "Offer 通知"}
          </span>
          <Badge tone={invite ? INVITE_TONES[invite.status] : OFFER_TONES[offer!.status]}>
            {invite ? invite.status_label : offer!.status_label}
          </Badge>
        </div>

        <div className="space-y-1 px-3 py-2.5 text-[11px] leading-relaxed">
          {invite ? (
            <>
              <DetailRow label="时间">
                {formatDateTime(invite.scheduled_at)}（{invite.duration_minutes} 分钟）
              </DetailRow>
              <DetailRow label="方式">
                {invite.mode_label}
                {invite.location ? ` · ${invite.location}` : ""}
              </DetailRow>
              {invite.note && <DetailRow label="说明">{invite.note}</DetailRow>}
              {invite.candidate_note && (
                <DetailRow label="候选人">{invite.candidate_note}</DetailRow>
              )}
            </>
          ) : (
            <>
              <DetailRow label="薪资">
                {offer!.salary_min}-{offer!.salary_max}K
              </DetailRow>
              <DetailRow label="入职">{offer!.start_date || "待定"}</DetailRow>
              {offer!.expires_at && (
                <DetailRow label="有效期">{formatDateTime(offer!.expires_at)}</DetailRow>
              )}
              {offer!.note && <DetailRow label="说明">{offer!.note}</DetailRow>}
              {offer!.response_note && (
                <DetailRow label="候选人">{offer!.response_note}</DetailRow>
              )}
            </>
          )}
        </div>

        {actions.length > 0 && (
          <div className="flex flex-wrap justify-end gap-2 border-t border-line px-3 py-2">
            {actions.map((action) => (
              <Button
                key={action.label}
                size="sm"
                variant={action.variant}
                loading={pending}
                onClick={action.run}
              >
                {action.label}
              </Button>
            ))}
          </div>
        )}

        {error && (
          <p className="border-t border-line px-3 py-2 text-[11px] text-danger">{error}</p>
        )}
      </div>
    </div>
  );
}
