import type { ReactNode } from "react";

/** 极简 Markdown 渲染：只支持 Agent 常用的粗体 / 行内代码 / 标题 / 列表，避免引入依赖。 */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    const key = `${keyPrefix}-${index}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={key} className="font-semibold text-ink">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={key} className="rounded bg-slate-100 px-1 py-0.5 text-[12px] text-slate-700">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

export function Markdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="my-1.5 space-y-1 pl-1">
        {listBuffer.map((item, index) => (
          <li key={index} className="flex gap-2">
            <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-slate-400" />
            <span>{renderInline(item, `li-${blocks.length}-${index}`)}</span>
          </li>
        ))}
      </ul>,
    );
    listBuffer = [];
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (/^#{1,4}\s/.test(trimmed)) {
      flushList();
      blocks.push(
        <p key={`h-${index}`} className="mb-1 mt-2 text-sm font-semibold text-ink">
          {renderInline(trimmed.replace(/^#{1,4}\s+/, ""), `h-${index}`)}
        </p>,
      );
    } else if (/^[-*•]\s+/.test(trimmed) || /^\d+[.、)]\s+/.test(trimmed)) {
      listBuffer.push(trimmed.replace(/^([-*•]|\d+[.、)])\s+/, ""));
    } else if (!trimmed) {
      flushList();
      blocks.push(<div key={`sp-${index}`} className="h-1.5" />);
    } else {
      flushList();
      blocks.push(
        <p key={`p-${index}`} className="leading-7">
          {renderInline(trimmed, `p-${index}`)}
        </p>,
      );
    }
  });
  flushList();

  return <div className="text-sm text-slate-700">{blocks}</div>;
}
