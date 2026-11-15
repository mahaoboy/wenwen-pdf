"use client";

import {
  DragEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";
import type { DocumentItem, QuotaInfo } from "@/lib/types";
import { Brand } from "@/components/Brand";
import { StatusBadge } from "@/components/StatusBadge";

export default function DocsPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [quota, setQuota] = useState<QuotaInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [docs, quotaInfo] = await Promise.all([
        api.listDocuments(),
        api.getQuota().catch(() => null),
      ]);
      setDocuments(docs);
      if (quotaInfo) setQuota(quotaInfo);
      setError("");
      void api.recordVisit().catch(() => undefined);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载文档列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    void load();
  }, [router, load]);

  const hasPending = documents.some(
    (doc) => doc.status === "pending" || doc.status === "parsing",
  );

  useEffect(() => {
    if (!hasPending) return;
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
  }, [hasPending, load]);

  async function handleRefresh() {
    setRefreshing(true);
    await load(true);
    setRefreshing(false);
  }

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file || uploading) return;

    setError("");
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("仅支持 PDF 文件");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError(`文件过大（${(file.size / 1024 / 1024).toFixed(1)}MB），单个 PDF 不超过 20MB`);
      return;
    }

    setUploading(true);
    try {
      const doc = await api.uploadDocument(file);
      setDocuments((prev) => [doc, ...prev]);
      void load(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "上传失败，请重试");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleReparse(docId: number) {
    setError("");
    try {
      await api.reparseDocument(docId);
      void load(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "重新解析失败");
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void handleFiles(event.dataTransfer.files);
  }

  async function handleDelete(doc: DocumentItem) {
    const confirmed = window.confirm(
      `确定删除「${doc.filename}」？切片、索引与对话记录将一并清除。`,
    );
    if (!confirmed) return;

    setDeletingId(doc.id);
    try {
      await api.deleteDocument(doc.id);
      setDocuments((prev) => prev.filter((item) => item.id !== doc.id));
      await load(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "删除失败，请重试");
    } finally {
      setDeletingId(null);
    }
  }

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-10 border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Brand />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void handleRefresh()}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
              title="刷新状态"
            >
              <svg
                className={`size-4 ${refreshing ? "animate-spin" : ""}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                <path d="M21 3v6h-6" />
              </svg>
              <span className="hidden sm:inline">刷新</span>
            </button>
            <Link
              href="/settings"
              className="rounded-lg px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
            >
              AI 设置
            </Link>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg px-3 py-2 text-sm text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
            >
              退出登录
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              我的文档
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {documents.length > 0
                ? `共 ${documents.length} 份文档，点击「开始对话」向文档提问。`
                : "上传 PDF 后即可开始提问。"}
            </p>
            {quota && (
              <p className="mt-2 text-xs text-slate-400">
                文档 {quota.doc_used}/{quota.doc_limit}
                <span className="mx-1.5 text-slate-300">·</span>
                提问 {quota.question_used}/{quota.question_limit}
                <span className="mx-1.5 text-slate-300">·</span>
                {quota.plan === "free" ? "免费版" : quota.plan}
              </p>
            )}
          </div>
        </div>

        {error && (
          <div
            role="alert"
            className="mt-5 flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600"
          >
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError("")}
              className="shrink-0 text-xs text-rose-400 hover:text-rose-600"
            >
              关闭
            </button>
          </div>
        )}

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          className={`mt-5 flex cursor-pointer items-center gap-3 rounded-xl border border-dashed px-4 py-3 transition ${
            dragging
              ? "border-accent bg-accent-wash"
              : "border-slate-300 bg-white hover:border-accent hover:bg-accent-wash/60"
          } ${uploading ? "pointer-events-none opacity-70" : ""}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={(event) => void handleFiles(event.target.files)}
          />
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent-wash text-accent">
            {uploading ? (
              <span className="size-4 animate-spin rounded-full border-2 border-accent/30 border-t-accent" />
            ) : (
              <svg
                className="size-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 16V4m0 0 4 4m-4-4L8 8" />
                <path d="M20 16v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-2" />
              </svg>
            )}
          </span>
          <p className="flex-1 truncate text-sm text-slate-600">
            {uploading ? (
              "正在上传…"
            ) : (
              <>
                拖入 PDF，或
                <span className="font-medium text-accent">点击选择文件</span>
                （≤20MB），自动解析与切片
              </>
            )}
          </p>
        </div>

        <section className="mt-6">
          {loading ? (
            <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
              {[0, 1, 2].map((index) => (
                <div key={index} className="flex items-center gap-3 px-4 py-4">
                  <div className="size-9 animate-pulse rounded-lg bg-slate-100" />
                  <div className="flex-1 space-y-2">
                    <div className="h-3.5 w-2/5 animate-pulse rounded bg-slate-100" />
                    <div className="h-3 w-1/4 animate-pulse rounded bg-slate-50" />
                  </div>
                </div>
              ))}
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center">
              <p className="text-sm font-medium text-slate-600">还没有文档</p>
              <p className="mt-1 text-sm text-slate-400">
                在上方拖入第一份 PDF，几秒后就能开始对话。
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="animate-fade-up flex items-center gap-3 px-4 py-3.5 transition hover:bg-accent-wash/40"
                >
                  <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent-wash text-accent">
                    <svg
                      className="size-4"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <path d="M14 2v6h6" />
                    </svg>
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h2
                        className="truncate text-sm font-medium text-slate-900"
                        title={doc.filename}
                      >
                        {doc.filename}
                      </h2>
                      <StatusBadge status={doc.status} />
                    </div>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {doc.page_count} 页
                      <span className="mx-1.5 text-slate-300">·</span>
                      {doc.chunk_count} 个切片
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-1.5">
                    {doc.status === "error" && (
                      <button
                        type="button"
                        onClick={() => void handleReparse(doc.id)}
                        className="rounded-lg px-2.5 py-1.5 text-xs text-accent transition hover:bg-accent-wash"
                      >
                        重新解析
                      </button>
                    )}
                    <Link
                      href={`/docs/${doc.id}`}
                      className={`inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                        doc.status === "ready"
                          ? "bg-accent text-white hover:bg-accent-deep"
                          : "border border-slate-200 text-slate-500 hover:border-accent hover:text-accent"
                      }`}
                    >
                      {doc.status === "ready" ? "开始对话" : "查看"}
                      <svg
                        className="size-3.5"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M5 12h14m-6-6 6 6-6 6" />
                      </svg>
                    </Link>
                    <button
                      type="button"
                      onClick={() => void handleDelete(doc)}
                      disabled={deletingId === doc.id}
                      className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-slate-400 transition hover:bg-rose-50 hover:text-rose-500 disabled:opacity-50"
                    >
                      {deletingId === doc.id ? (
                        <span className="size-3.5 animate-spin rounded-full border-2 border-slate-200 border-t-rose-400" />
                      ) : (
                        <svg
                          className="size-3.5"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                          <path d="M10 11v6M14 11v6" />
                        </svg>
                      )}
                      删除
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
