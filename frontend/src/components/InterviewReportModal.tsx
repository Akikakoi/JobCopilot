import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Interview } from "../lib/types";
import { InterviewReportView } from "./InterviewReportView";
import { Button, Modal, Skeleton } from "./ui";

export function InterviewReportModal({
  open,
  applicationId,
  candidateName,
  onClose,
}: {
  open: boolean;
  applicationId: number;
  candidateName: string;
  onClose: () => void;
}) {
  const reportQuery = useQuery({
    queryKey: ["interview-report", applicationId],
    queryFn: () => api.get<Interview | null>(`/interviews/application/${applicationId}`),
    enabled: open && applicationId > 0,
  });

  return (
    <Modal
      open={open}
      title={`AI 面试报告 · ${candidateName}`}
      width="max-w-3xl"
      onClose={onClose}
      footer={<Button onClick={onClose}>关闭</Button>}
    >
      {reportQuery.isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-36 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}
      {reportQuery.isError && (
        <p className="rounded-xl bg-[#FDECEC] px-3.5 py-2.5 text-xs text-danger">
          {(reportQuery.error as Error).message}
        </p>
      )}
      {reportQuery.data === null && (
        <div className="rounded-xl border border-dashed border-line px-4 py-10 text-center">
          <p className="text-sm font-medium">候选人尚未完成 AI 模拟面试</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            候选人可在「面试训练」中针对该岗位完成作答并生成报告，完成后这里会自动展示。
          </p>
        </div>
      )}
      {reportQuery.data && <InterviewReportView interview={reportQuery.data} />}
    </Modal>
  );
}
