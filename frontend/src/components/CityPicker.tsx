import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronIcon } from "./icons";
import { cn } from "./ui";
import { CITIES, CITY_INITIALS, HOT_CITIES, PROVINCE_CITIES } from "../lib/jobMeta";

/**
 * 城市选择器：热门城市 + 按拼音首字母分组的全量城市。
 * 面板通过 Portal 渲染到 body，避免被父级层叠上下文或滚动容器裁剪。
 */
export function CityPicker({
  value,
  onChange,
  className,
  ariaLabel = "城市",
  placeholder = "全部城市",
}: {
  value: string;
  onChange: (city: string) => void;
  className?: string;
  ariaLabel?: string;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [province, setProvince] = useState("");
  const [provinceOpen, setProvinceOpen] = useState(false);
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
    const map: Record<string, string[]> = {};
    CITIES.forEach((city) => {
      const letter = CITY_INITIALS[city] || "#";
      (map[letter] ||= []).push(city);
    });
    return Object.keys(map)
      .sort()
      .map((letter) => ({ letter, cities: map[letter] }));
  }, []);

  const openPanel = () => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const width = Math.min(520, window.innerWidth - 24);
    const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
    const spaceBelow = window.innerHeight - rect.bottom - 12;
    const spaceAbove = rect.top - 12;
    const flipUp = spaceBelow < 360 && spaceAbove > spaceBelow;
    setPos({
      left,
      width,
      top: flipUp ? undefined : rect.bottom + 6,
      bottom: flipUp ? window.innerHeight - rect.top + 6 : undefined,
      maxHeight: Math.max(280, Math.min(520, flipUp ? spaceAbove : spaceBelow)),
    });
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

  const choose = (city: string) => {
    onChange(city);
    setOpen(false);
  };

  const scrollToGroup = (letter: string) => {
    const container = panelRef.current;
    const target = container?.querySelector<HTMLElement>(`[data-group="${letter}"]`);
    if (!container || !target) return;
    const offset =
      target.getBoundingClientRect().top -
      container.getBoundingClientRect().top +
      container.scrollTop -
      4;
    container.scrollTo({ top: offset, behavior: "smooth" });
  };

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
        <span className={cn("truncate", !value && "text-muted")}>{value || placeholder}</span>
        <ChevronIcon className={cn("h-3.5 w-3.5 shrink-0", open ? "text-primary" : "text-muted")} />
      </button>

      {open &&
        pos &&
        createPortal(
          <div
            ref={panelRef}
            role="dialog"
            aria-label="选择城市"
            style={{
              left: pos.left,
              width: pos.width,
              top: pos.top,
              bottom: pos.bottom,
              maxHeight: pos.maxHeight,
            }}
            className="fixed z-50 overflow-y-auto rounded-xl border border-line bg-surface p-4 shadow-md animate-fade-in"
          >
            <p className="text-xs font-semibold text-muted">热门城市</p>
            <div className="mt-2 grid grid-cols-5 gap-1.5">
              <button
                type="button"
                onClick={() => choose("")}
                className={cn(
                  "rounded-lg px-2 py-1.5 text-xs transition-colors",
                  value === ""
                    ? "bg-primary-soft font-medium text-primary"
                    : "bg-neutral-soft text-ink hover:text-primary",
                )}
              >
                全国
              </button>
              {HOT_CITIES.map((city) => (
                <button
                  key={city}
                  type="button"
                  onClick={() => choose(city)}
                  className={cn(
                    "rounded-lg px-2 py-1.5 text-xs transition-colors",
                    value === city
                      ? "bg-primary-soft font-medium text-primary"
                      : "bg-neutral-soft text-ink hover:text-primary",
                  )}
                >
                  {city}
                </button>
              ))}
              <button
                type="button"
                onClick={() => choose("远程")}
                className={cn(
                  "rounded-lg px-2 py-1.5 text-xs transition-colors",
                  value === "远程"
                    ? "bg-primary-soft font-medium text-primary"
                    : "bg-neutral-soft text-ink hover:text-primary",
                )}
              >
                远程
              </button>
            </div>

            <div className="mt-3 border-t border-line pt-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-muted">按省份选择</span>
                <button
                  type="button"
                  onClick={() => setProvinceOpen((prev) => !prev)}
                  className="flex w-[180px] items-center justify-between gap-2 rounded-lg border border-line px-2.5 py-1.5 text-xs transition-colors hover:border-muted"
                >
                  <span className={cn(!province && "text-muted")}>{province || "选择省份"}</span>
                  <ChevronIcon className={cn("h-3 w-3 shrink-0", provinceOpen ? "text-primary" : "text-muted")} />
                </button>
              </div>
              {provinceOpen && (
                <div className="mt-2 grid grid-cols-6 gap-1.5">
                  {Object.keys(PROVINCE_CITIES).map((name) => (
                    <button
                      key={name}
                      type="button"
                      onClick={() => {
                        setProvince(name);
                        setProvinceOpen(false);
                      }}
                      className={cn(
                        "rounded-lg px-2 py-1.5 text-xs transition-colors",
                        province === name
                          ? "bg-primary-soft font-medium text-primary"
                          : "bg-neutral-soft text-ink hover:text-primary",
                      )}
                    >
                      {name}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {province ? (
              <div className="mt-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-muted">{province} · 城市</p>
                  <button
                    type="button"
                    onClick={() => setProvince("")}
                    className="text-xs text-primary hover:underline"
                  >
                    查看全部城市
                  </button>
                </div>
                <div className="mt-2 grid grid-cols-5 gap-1.5">
                  {PROVINCE_CITIES[province].map((city) => (
                    <button
                      key={city}
                      type="button"
                      onClick={() => choose(city)}
                      className={cn(
                        "rounded-lg px-2 py-1.5 text-xs transition-colors",
                        value === city
                          ? "bg-primary-soft font-medium text-primary"
                          : "bg-neutral-soft text-ink hover:text-primary",
                      )}
                    >
                      {city}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div className="mt-4 flex items-start gap-2 border-t border-line pt-3">
                  <span className="shrink-0 pt-0.5 text-xs text-muted">按字母选择</span>
                  <div className="flex flex-wrap gap-x-2 gap-y-1">
                    {groups.map((group) => (
                      <button
                        key={group.letter}
                        type="button"
                        onClick={() => scrollToGroup(group.letter)}
                        className="w-4 text-center text-xs text-muted transition-colors hover:text-primary"
                      >
                        {group.letter}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-1">
                  {groups.map((group) => (
                    <div
                      key={group.letter}
                      data-group={group.letter}
                      className="flex gap-3 border-b border-line/70 py-2 last:border-0"
                    >
                      <span className="w-5 shrink-0 text-sm font-semibold text-muted">{group.letter}</span>
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        {group.cities.map((city) => (
                          <button
                            key={city}
                            type="button"
                            onClick={() => choose(city)}
                            className={cn(
                              "rounded px-1 text-sm transition-colors hover:text-primary",
                              value === city ? "font-medium text-primary" : "text-ink",
                            )}
                          >
                            {city}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>,
          document.body,
        )}
    </div>
  );
}
