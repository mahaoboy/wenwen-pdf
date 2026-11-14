import Link from "next/link";

export function Brand({ className = "" }: { className?: string }) {
  return (
    <Link href="/docs" className={`inline-flex items-center gap-2.5 ${className}`}>
      <span className="grid size-9 place-items-center rounded-xl bg-linear-to-br from-emerald-500 to-teal-600 text-base font-bold text-white shadow-sm shadow-emerald-500/30">
        文
      </span>
      <span className="text-lg font-semibold tracking-tight text-slate-900">
        文问
        <span className="ml-1.5 text-sm font-normal text-slate-400">WenWen</span>
      </span>
    </Link>
  );
}
