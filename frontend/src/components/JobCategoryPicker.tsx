import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CheckIcon, ChevronIcon } from "./icons";
import { cn } from "./ui";
import { JOB_CATEGORIES } from "../lib/jobMeta";

interface CategoryOption {
  category?: string;
  subcategory?: string;
}

/**
 * 岗位类别 + 方向的两级选择器：一个触发器，面板左侧选类别、右侧选方向。
 * 面板通过 Portal 渲染到 body，避免被父级层叠上下文或滚动容器裁剪。
 */
export function JobCategoryPicker({
  category,
  subcategory,
  onChange,
  jobs,
  placeholder = "选择岗位类别与方向",
  className,
  ariaLabel = "目标岗位类别与方向",
}: {
  category: string;
  subcategory: string;
  onChange: (category: string, subcategory: string) => void;
  jobs: CategoryOption[];
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
    const map = new Map<string, Map<string, number>>();
    JOB_CATEGORIES.forEach((item) => map.set(item, new Map()));
    jobs.forEach((job) => {
      const jobCategory =
        job.category && JOB_CATEGORIES.includes(job.category) ? job.category : "其他";
      const subcategories = map.get(jobCategory)!;
      const sub = job.subcategory || "其他";
      subcategories.set(sub, (subcategories.get(sub) || 0) + 1);
    });
    return Array.from(map.entries())
      .map(([name, subcategories]) => ({
        name,
        total: Array.from(subcategories.values()).reduce((sum, count) => sum + count, 0),
        directions: Array.from(subcategories.entries()).sort((a, b) => b[1] - a[1]),
      }))
      .filter((group) => group.total > 0);
  }, [jobs]);

  const activeGroup = groups.find((group) => group.name === activeCategory);

  const openPanel = () => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.min(440, window.innerWidth - 24);
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const flipUp = spaceBelow < 340 && spaceAbove > spaceBelow;
    setPos({
      left,
      width,
      top: flipUp ? undefined : rect.bottom + 6,
      bottom: flipUp ? window.innerHeight - rect.top + 6 : undefined,
      maxHeight: Math.max(260, Math.min(440, flipUp ? spaceAbove : spaceBelow)),
    });
    setActiveCategory(category || groups[0]?.name || "");
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

  const commit = (nextCategory: string, nextSubcategory: string) => {
    onChange(nextCategory, nextSubcategory);
    setOpen(false);
  };

  const label = category ? `${category} · ${subcategory || "全部方向"}` : "";

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
        <span className={cn("truncate", !label && "text-muted")}>{label || placeholder}</span>
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
            <div className="w-[150px] shrink-0 overflow-y-auto border-r border-line py-2">
              {groups.map((group) => (
                <button
                  key={group.name}
                  type="button"
                  onMouseEnter={() => setActiveCategory(group.name)}
                  onClick={() => setActiveCategory(group.name)}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 px-4 py-2 text-left text-sm transition-colors",
                    activeCategory === group.name
                      ? "bg-primary-soft font-medium text-primary"
                      : "text-ink hover:bg-neutral-soft",
                  )}
                >
                  <span className="truncate">{group.name}</span>
                  <span className="shrink-0 text-[10px] tabular-nums text-muted">{group.total}</span>
                </button>
              ))}
            </div>

            <div className="min-w-0 flex-1 overflow-y-auto p-2">
              {activeGroup ? (
                <>
                  <button
                    type="button"
                    onClick={() => commit(activeGroup.name, "")}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-left text-sm transition-colors",
                      category === activeGroup.name && !subcategory
                        ? "bg-primary-soft font-medium text-primary"
                        : "text-ink hover:bg-neutral-soft",
                    )}
                  >
                    <span>全部方向</span>
                    <span className="flex shrink-0 items-center gap-2 text-[11px] tabular-nums text-muted">
                      {activeGroup.total}
                      {category === activeGroup.name && !subcategory && (
                        <CheckIcon className="h-3.5 w-3.5" />
                      )}
                    </span>
                  </button>
                  <div className="my-1 border-t border-line" />
                  {activeGroup.directions.map(([direction, count]) => {
                    const isSelected = category === activeGroup.name && subcategory === direction;
                    return (
                      <button
                        key={direction}
                        type="button"
                        onClick={() => commit(activeGroup.name, direction)}
                        title={direction}
                        className={cn(
                          "flex w-full items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-left text-sm transition-colors",
                          isSelected
                            ? "bg-primary-soft font-medium text-primary"
                            : "text-ink hover:bg-neutral-soft",
                        )}
                      >
                        <span className="truncate">{direction}</span>
                        <span className="flex shrink-0 items-center gap-2 text-[11px] tabular-nums text-muted">
                          {count}
                          {isSelected && <CheckIcon className="h-3.5 w-3.5" />}
                        </span>
                      </button>
                    );
                  })}
                </>
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