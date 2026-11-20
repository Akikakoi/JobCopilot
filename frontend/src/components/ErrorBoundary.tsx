import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[JobCopilot] 页面渲染异常", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-full items-center justify-center bg-bg px-6 py-16">
          <div className="w-full max-w-md rounded-2xl border border-line bg-white p-8 text-center shadow-sm">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FDECEC] text-xl text-danger">
              !
            </div>
            <h1 className="mt-4 text-lg font-semibold">页面出了点问题</h1>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              {this.state.error.message || "未知错误"}。可以刷新重试；如果持续出现，请查看浏览器控制台。
            </p>
            <button className="btn btn-primary mt-6 w-full" onClick={() => window.location.reload()}>
              刷新页面
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
