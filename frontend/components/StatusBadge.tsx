import type { DocumentStatus } from "@/lib/types";

const STATUS_MAP: Record<
  string,
  { label: string; className: string; pulse?: boolean }
> = {
  pending: {
    label: "等待解析",
    className: "bg-slate-100 text-slate-600",
  },
  parsing: {
    label: "解析中",
    className: "bg-amber-50 text-amber-600",
    pulse: true,
  },
  ready: {
    label: "已就绪",
    className: "bg-emerald-50 text-emerald-600",
  },
  error: {
    label: "解析失败",
    className: "bg-rose-50 text-rose-600",
  },
};

export function StatusBadge({ status }: { status: DocumentStatus | string }) {
  const item = STATUS_MAP[status] ?? {
    label: status,
    className: "bg-slate-100 text-slate-600",
  };

  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${item.className}`}
    >
      <span
        className={`size-1.5 rounded-full bg-current ${item.pulse ? "animate-pulse" : ""}`}
      />
      {item.label}
    </span>
  );
}
