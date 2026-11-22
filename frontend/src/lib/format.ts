/** 日期时间格式化：全量显示（年月日时分秒）与短格式（月日时分）。 */

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-CN");
}

export function formatShortDateTime(value: string | null | undefined): string {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
