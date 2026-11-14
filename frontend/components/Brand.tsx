import Link from "next/link";

export function Brand({
  className = "",
  href = "/docs",
}: {
  className?: string;
  href?: string;
}) {
  return (
    <Link href={href} className={`inline-flex items-center gap-2.5 ${className}`}>
      {/* 印章：批注红方块 + 白字「文」——品牌唯一记忆点 */}
      <span className="grid size-9 place-items-center rounded-lg bg-accent text-base font-bold text-white shadow-sm shadow-accent/25">
        文
      </span>
      <span className="text-lg font-semibold tracking-tight text-slate-900">
        文问
        <span className="ml-1.5 text-sm font-normal text-slate-400">WenWen</span>
      </span>
    </Link>
  );
}
