import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import {
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "soft" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cn(
        "btn",
        variant === "primary" && "btn-primary",
        variant === "ghost" && "btn-ghost",
        variant === "soft" && "btn-soft",
        variant === "danger" && "bg-danger text-white hover:bg-red-700",
        size === "sm" && "px-3 py-1.5 text-xs",
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
      )}
      {children}
    </button>
  );
}

export function Card({
  className,
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("card", className)} {...rest}>
      {children}
    </div>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("input", className)} {...rest} />;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("input min-h-[96px] resize-y", className)} {...rest} />;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <p className="mt-1.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

export function Badge({
  tone = "default",
  children,
  className,
}: {
  tone?: "default" | "primary" | "success" | "warning" | "danger";
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "chip",
        tone === "primary" && "chip-primary",
        tone === "success" && "chip-success",
        tone === "warning" && "chip-warning",
        tone === "danger" && "chip-danger",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-xl", className)} />;
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-white/60 px-6 py-16 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-xl text-slate-400">
        ◍
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ScoreRing({
  score,
  size = 132,
  label = "匹配度",
}: {
  score: number;
  size?: number;
  label?: string;
}) {
  const [display, setDisplay] = useState(0);
  const rounded = Math.round(score);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setDisplay(rounded);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const duration = 720;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(rounded * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [rounded]);

  const radius = size / 2 - 9;
  const circumference = 2 * Math.PI * radius;
  const ratio = Math.max(0, Math.min(1, score / 100));
  const color =
    score >= 80 ? "var(--success)" : score >= 60 ? "var(--primary)" : "var(--warning)";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#EAF0FB"
          strokeWidth={9}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={9}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - ratio)}
          style={{ transition: "stroke-dashoffset 700ms var(--ease-out)" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold tabular-nums tracking-tight" style={{ color }}>
          {display}
        </span>
        <span className="mt-0.5 text-[11px] font-medium text-muted">{label}</span>
      </div>
    </div>
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  width = "max-w-lg",
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/35 p-4 backdrop-blur-[2px] animate-fade-in"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        className={cn(
          "w-full animate-scale-in rounded-3xl border border-line bg-white shadow-md",
          width,
        )}
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h3 className="text-base font-semibold text-ink">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-muted transition-colors hover:bg-slate-100 hover:text-ink"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
        <div className="max-h-[65vh] overflow-y-auto px-6 py-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>
        )}
      </div>
    </div>
  );
}

export function ProgressBar({
  value,
  max,
  tone = "primary",
}: {
  value: number;
  max: number;
  tone?: "primary" | "success" | "warning";
}) {
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-700",
          tone === "primary" && "bg-primary",
          tone === "success" && "bg-success",
          tone === "warning" && "bg-warning",
        )}
        style={{ width: `${ratio * 100}%`, transitionTimingFunction: "var(--ease-out)" }}
      />
    </div>
  );
}

export const STATUS_META: Record<string, { label: string; tone: "default" | "primary" | "success" | "warning" | "danger" }> = {
  submitted: { label: "已投递", tone: "default" },
  screening: { label: "筛选中", tone: "primary" },
  interview: { label: "面试中", tone: "warning" },
  offer: { label: "已录用", tone: "success" },
  rejected: { label: "未通过", tone: "danger" },
  open: { label: "在招", tone: "success" },
  closed: { label: "已关闭", tone: "default" },
};
