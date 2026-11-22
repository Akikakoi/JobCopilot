import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CheckIcon, ChevronIcon } from "./icons";
import { cn } from "./ui";
import { JOB_CATEGORIES } from "../lib/jobMeta";

interface JobOption {
  id: number;
  title: string;
  company_name?: string;
  category?: string;
}

/**
 * 岗位选择器：左侧大类、右侧岗位列表的两级菜单。
 * 面板通过 Portal 渲染到 body，避免被父级层叠上下文或滚动容器裁剪。
 */
export function JobPicker({
  value,
  onChange,
  jobs,
  placeholder = "选择目标岗位",
  className,
  ariaLabel = "目标岗位",
}: {
  value: string;
  onChange: (jobId: string) => void;
  jobs: JobOption[];
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}) {
  const [open, setOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState("");
  const [pos, setPos] = useState<{
    left: number;
    width: number;
    top?: number;
    bottom?: number;
    maxHeight: number;
  } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const groups = useMemo(() => {
    const map = new Map<string, JobOption[]>();
    JOB_CATEGORIES.forEach((category) => map.set(category, []));
    jobs.forEach((job) => {
      const category = job.category && JOB_CATEGORIES.includes(job.category) ? job.category : "其他";
      map.get(category)!.push(job);
    });
    return Array.from(map.entries()).filter(([, items]) => items.length > 0);
  }, [jobs]);

  const current = jobs.find((job) => String(job.id) === value);
  const currentCategory =
    current && current.category && JOB_CATEGORIES.includes(current.category)
      ? current.category
      : "";

  const openPanel = () => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.min(640, window.innerWidth - 24);
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const flipUp = spaceBelow < 360 && spaceAbove > spaceBelow;
    setPos({
      left,
      width,
      top: flipUp ? undefined : rect.bottom + 6,
      bottom: flipUp ? window.innerHeight - rect.top + 6 : undefined,
      maxHeight: Math.max(280, Math.min(460, flipUp ? spaceAbove : spaceBelow)),
    });
    setActiveCategory(currentCategory || groups[0]?.[0] || "");
    setOpen(true);
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !panelRef.current?.contains(target)) {
        setOpen(false);
      }
    };
    // 面板内部滚动不关闭，仅页面滚动时收起
    const onScroll = (event: Event) => {
      if (panelRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    const onResize = () => setOpen(false);
    document.addEventListener("mousedown", onPointerDown);
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onResize);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
    };
  }, [open]);

  const choose = (job: JobOption) => {
    onChange(String(job.id));
    setOpen(false);
  };

  const items = groups.find(([category]) => category === activeCategory)?.[1] || [];
  const columns = pos && pos.width >= 560 ? 3 : 2;

  return (
    <div className={className}>
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ariaLabel}
        onClick={() => (open ? setOpen(false) : openPanel())}
        onKeyDown={(event) => {
          if (event.key === "Escape") setOpen(false);
        }}
        className={cn("input flex items-center justify-between gap-2 text-left", open && "border-primary")}
      >
        <span className={cn("truncate", !current && "text-muted")}>
          {current ? `${current.title}${current.company_name ? ` · ${current.company_name}` : ""}` : placeholder}
        </span>
        <ChevronIcon className={cn("h-3.5 w-3.5 shrink-0", open ? "text-primary" : "text-muted")} />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label={ariaLabel}
            style={{
              left: pos.left,
              width: pos.width,
              top: pos.top,
              bottom: pos.bottom,
              maxHeight: pos.maxHeight,
            }}
            className="fixed z-50 flex overflow-hidden rounded-xl border border-line bg-surface shadow-md animate-fade-in"
          >
            <div className="w-[160px] shrink-0 overflow-y-auto border-r border-line py-2">
              {groups.map(([category, jobItems]) => (
                <button
                  key={category}
                  type="button"
                  onMouseEnter={() => setActiveCategory(category)}
                  onClick={() => setActiveCategory(category)}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 px-4 py-2 text-left text-sm transition-colors",
                    activeCategory === category
                      ? "bg-primary-soft font-medium text-primary"
                      : "text-ink hover:bg-neutral-soft",
                  )}
                >
                  <span className="truncate">{category}</span>
                  <span className="shrink-0 text-[10px] tabular-nums text-muted">{jobItems.length}</span>
                </button>
              ))}
            </div>

            <div className="min-w-0 flex-1 overflow-y-auto p-3">
              {items.length > 0 ? (
                <div
                  className="grid gap-x-1 gap-y-0.5"
                  style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}
                >
                  {items.map((job) => {
                    const isSelected = String(job.id) === value;
                    return (
                      <button
                        key={job.id}
                        type="button"
                        title={`${job.title}${job.company_name ? ` · ${job.company_name}` : ""}`}
                        onClick={() => choose(job)}
                        className={cn(
                          "flex w-full items-center justify-between gap-1 rounded-lg px-2.5 py-1.5 text-left transition-colors",
                          isSelected
                            ? "bg-primary-soft text-primary"
                            : "text-ink hover:bg-neutral-soft",
                        )}
                      >
                        <span className="min-w-0 flex-1">
                          <span className={cn("block truncate text-sm", isSelected && "font-medium")}>
                            {job.title}
                          </span>
                          {job.company_name && (
                            <span className="block truncate text-[11px] text-muted">
                              {job.company_name}
                            </span>
                          )}
                        </span>
                        {isSelected && <CheckIcon className="h-3.5 w-3.5 shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="px-2 py-8 text-center text-xs text-muted">该类别暂无在招岗位</p>
              )}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
