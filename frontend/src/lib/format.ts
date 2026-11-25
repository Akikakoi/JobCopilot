/** 日期时间格式化：全量显示（年月日时分秒）与短格式（月日时分）。 */

const ZONE_SUFFIX = /(Z|[+-]\d{2}:?\d{2})$/i;

/** 服务端存储的是 UTC naive 时间（如 2026-11-24T08:30:00），按 UTC 解析避免显示偏移。 */
export function parseServerDate(value: string): Date {
  const needZone = value.includes("T") && !ZONE_SUFFIX.test(value);
  return new Date(needZone ? `${value}Z` : value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return parseServerDate(value).toLocaleString("zh-CN");
}

export function formatShortDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return parseServerDate(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** datetime-local / date 输入值（浏览器本地时区）→ UTC ISO，供服务端存储。 */
export function localInputToUtcIso(value: string): string {
  return new Date(value).toISOString();
}

/** 服务端 UTC naive 时间 → 本地 YYYY-MM-DD，用于回填 date 输入。 */
export function toLocalDateInput(value: string | null | undefined): string {
  if (!value) return "";
  const date = parseServerDate(value);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}