import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { createPortal } from "react-dom";
import { CheckIcon, ChevronIcon, CloseIcon } from "./icons";
import {
  useEffect,
  useLayoutEffect,
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

type SelectOption = { label: string; value: string };

export function Select({
  value,
  onChange,
  options,
  placeholder,
  className,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [pos, setPos] = useState<{
    left: number;
    width: number;
    top?: number;
    bottom?: number;
    maxHeight: number;
  } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const selectedIndex = options.findIndex((option) => option.value === value);
  const current = selectedIndex >= 0 ? options[selectedIndex] : undefined;

  const openMenu = () => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const flipUp = spaceBelow < 220 && spaceAbove > spaceBelow;
    setPos({
      left: rect.left,
      width: rect.width,
      top: flipUp ? undefined : rect.bottom + 6,
      bottom: flipUp ? window.innerHeight - rect.top + 6 : undefined,
      maxHeight: Math.max(160, Math.min(320, flipUp ? spaceAbove : spaceBelow)),
    });
    setActive(selectedIndex);
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !listRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    const close = () => setOpen(false);
    // 面板内部的滚动（滚轮/拖动滚动条）不应关闭面板
    const onScroll = (event: Event) => {
      if (listRef.current?.contains(event.target as Node)) return;
      close();
    };
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("resize", close);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("resize", close);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open || active < 0) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const commit = (index: number) => {
    const option = options[index];
    if (!option) return;
    onChange(option.value);
    setOpen(false);
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        openMenu();
        return;
      }
      const delta = event.key === "ArrowDown" ? 1 : -1;
      setActive((prev) => {
        if (prev < 0) return delta === 1 ? 0 : options.length - 1;
        return (prev + delta + options.length) % options.length;
      });
      return;
    }
    if (open && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      commit(active);
      return;
    }
    if (event.key === "Escape") setOpen(false);
  };

  return (
    <div className={className}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => (open ? setOpen(false) : openMenu())}
        onKeyDown={onKeyDown}
        className={cn("input flex items-center justify-between gap-2 text-left", open && "border-primary")}
      >
        <span className={cn("truncate", !current && "text-muted")}>
          {current?.label ?? placeholder ?? ""}
        </span>
        <ChevronIcon className={cn("h-3.5 w-3.5 shrink-0", open ? "text-primary" : "text-muted")} />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={listRef}
            role="listbox"
            style={{
              left: pos.left,
              width: pos.width,
              top: pos.top,
              bottom: pos.bottom,
              maxHeight: pos.maxHeight,
            }}
            className="fixed z-50 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-md animate-fade-in"
          >
            {options.map((option, index) => {
              const isSelected = option.value === value;
              return (
                <button
                  key={option.value || "__all"}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  data-index={index}
                  onClick={() => commit(index)}
                  onMouseEnter={() => setActive(index)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-lg px-3 py-1.5 text-left text-sm transition-colors",
                    isSelected
                      ? "bg-primary-soft font-medium text-primary"
                      : index === active
                        ? "bg-neutral-soft text-ink"
                        : "text-ink",
                  )}
                >
                  <span className="truncate">{option.label}</span>
                  {isSelected && <CheckIcon className="h-3.5 w-3.5 shrink-0" />}
                </button>
              );
            })}
          </div>,
          document.body,
        )}
    </div>
  );
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
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-surface px-6 py-16 text-center">
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
          stroke="var(--neutral-soft)"
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
  const bodyRef = useRef<HTMLDivElement>(null);

  // 部分浏览器会因 iframe/表单控件聚焦把弹窗内容滚到下方，打开时统一归零
  useLayoutEffect(() => {
    if (!open) return;
    if (bodyRef.current) {
      bodyRef.current.scrollTop = 0;
      bodyRef.current.scrollLeft = 0;
    }
  }, [open]);

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fade-in"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        className={cn(
          "w-full animate-fade-in rounded-2xl border border-line bg-surface shadow-md",
          width,
        )}
      >
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h3 className="text-base font-semibold text-ink">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted transition-colors hover:bg-neutral-soft hover:text-ink"
            aria-label="关闭"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>
        <div ref={bodyRef} className="max-h-[65vh] overflow-y-auto px-6 py-5">{children}</div>
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
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-soft">
      <div
        className={cn(
          "h-full rounded-full transition-[width] duration-500",
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
  offer: { label: "Offer 阶段", tone: "warning" },
  onboarding: { label: "待入职", tone: "primary" },
  hired: { label: "已入职", tone: "success" },
  abandoned: { label: "放弃入职", tone: "default" },
  rejected: { label: "未通过", tone: "danger" },
  open: { label: "在招", tone: "success" },
  closed: { label: "已关闭", tone: "default" },
};
