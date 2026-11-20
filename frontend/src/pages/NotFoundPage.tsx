import { Link } from "react-router-dom";
import { homePath, useAuth } from "../lib/auth";

export function NotFoundPage() {
  const { user } = useAuth();
  const target = user ? homePath(user.role) : "/login";

  return (
    <div className="flex min-h-full items-center justify-center bg-bg px-6 py-16">
      <div className="w-full max-w-md text-center">
        <p className="text-[64px] font-semibold leading-none tracking-tight text-neutral-soft-2">404</p>
        <h1 className="mt-2 text-lg font-semibold">这个页面不存在</h1>
        <p className="mt-2 text-xs leading-relaxed text-muted">
          链接可能已失效，或者地址输错了。回到首页继续找工作或招人。
        </p>
        <Link to={target} className="btn btn-primary mt-6 inline-flex">
          回到首页
        </Link>
      </div>
    </div>
  );
}
