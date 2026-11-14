"use client";

import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { ChatMessage, Citation, DocumentItem } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

const SUGGESTIONS = [
  "这份文档的主要内容是什么？",
  "文档中有哪些关键条款或结论？",
  "用三点总结这份文档。",
];

function sessionKey(docId: number) {
  return `wenwen_session_${docId}`;
}

function getSessionId(docId: number): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(sessionKey(docId));
}

function saveSessionId(docId: number, sessionId: string) {
  window.localStorage.setItem(sessionKey(docId), sessionId);
}

function AssistantAvatar() {
  return (
    <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-linear-to-br from-emerald-500 to-teal-600 text-xs font-bold text-white shadow-sm shadow-emerald-500/25">
      文
    </span>
  );
}

function Citations({ citations }: { citations: Citation[] }) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!citations || citations.length === 0) return null;
  const active = openIndex === null ? null : citations[openIndex];

  return (
    <div className="mt-3 border-t border-slate-100 pt-3">
      <p className="mb-2 text-xs font-medium text-slate-400">引用来源</p>
      <div className="flex flex-wrap gap-2">
        {citations.map((citation, index) => (
          <button
            key={`${citation.chunk_id}-${index}`}
            type="button"
            onClick={() =>
              setOpenIndex(openIndex === index ? null : index)
            }
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
              openIndex === index
                ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                : "border-slate-200 bg-white text-slate-500 hover:border-emerald-200 hover:text-emerald-600"
            }`}
            title="点击查看原文片段"
          >
            <span className="grid size-4 place-items-center rounded-full bg-emerald-100 text-[10px] font-semibold text-emerald-700">
              {index + 1}
            </span>
            第 {citation.page} 页
          </button>
        ))}
      </div>
      {active && (
        <blockquote className="mt-2 animate-fade-up rounded-xl border-l-2 border-emerald-400 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
          「{active.snippet}」
          <span className="mt-1 block text-[10px] text-slate-400">
            切片 {active.chunk_id}
          </span>
        </blockquote>
      )}
    </div>
  );
}

export default function ChatPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const docId = Number(params?.id);

  const [doc, setDoc] = useState<DocumentItem | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [chatError, setChatError] = useState("");
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!Number.isInteger(docId) || docId <= 0) {
      setError("文档不存在");
      setLoading(false);
      return;
    }

    try {
      const [docs, initialHistory] = await Promise.all([
        api.listDocuments(),
        api.listMessages(docId, getSessionId(docId)),
      ]);
      const found = docs.find((item) => item.id === docId) ?? null;
      if (!found) {
        setError("文档不存在或已被删除");
      }
      setDoc(found);

      let sid = getSessionId(docId);
      let history = initialHistory;
      if (!sid && history.length > 0) {
        // 没有本地会话记录时，接管该文档最近一次会话，保证多轮上下文连续
        sid = history[history.length - 1].session_id || null;
        if (sid) {
          history = history.filter((item) => item.session_id === sid);
          saveSessionId(docId, sid);
        }
      }
      setSessionId(sid);
      setMessages(history);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载对话失败");
    } finally {
      setLoading(false);
    }
  }, [docId, router]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!doc || (doc.status !== "pending" && doc.status !== "parsing")) return;
    const timer = window.setInterval(async () => {
      try {
        const docs = await api.listDocuments();
        const found = docs.find((item) => item.id === docId);
        if (found) setDoc(found);
      } catch {
        // 轮询失败静默处理，等待下一轮
      }
    }, 3000);
    return () => window.clearInterval(timer);
  }, [doc, docId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, sending]);

  const ready = doc?.status === "ready";
  const canAsk = ready && !sending;

  async function send(raw: string) {
    const question = raw.trim();
    if (!question || sending) return;

    if (!ready) {
      setChatError("文档尚未解析完成，请稍候再提问");
      return;
    }

    const optimistic: ChatMessage = {
      role: "user",
      content: question,
      citations: [],
    };

    setInput("");
    setChatError("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setSending(true);
    setMessages((prev) => [...prev, optimistic]);

    try {
      const response = await api.chat(docId, question, sessionId);
      if (response.session_id) {
        setSessionId(response.session_id);
        saveSessionId(docId, response.session_id);
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.answer,
          citations: response.citations ?? [],
        },
      ]);
    } catch (err) {
      setMessages((prev) => prev.filter((item) => item !== optimistic));
      setInput((current) => current || question);
      setChatError(err instanceof ApiError ? err.message : "发送失败，请重试");
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(input);
  }

  function handleInputChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setInput(event.target.value);
    const element = event.target;
    element.style.height = "auto";
    element.style.height = `${Math.min(element.scrollHeight, 160)}px`;
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void send(input);
    }
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="shrink-0 border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4 sm:px-6">
          <Link
            href="/docs"
            aria-label="返回文档列表"
            className="grid size-9 shrink-0 place-items-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
          >
            <svg
              className="size-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M19 12H5m6 6-6-6 6-6" />
            </svg>
          </Link>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1
                className="truncate text-sm font-semibold text-slate-900"
                title={doc?.filename}
              >
                {doc?.filename ?? "加载中…"}
              </h1>
              {doc && <StatusBadge status={doc.status} />}
            </div>
            <p className="mt-0.5 text-xs text-slate-400">
              {doc
                ? `${doc.page_count} 页 · ${doc.chunk_count} 个切片 · 答案附带原文引用`
                : "正在获取文档信息…"}
            </p>
          </div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="mx-auto max-w-3xl space-y-5 px-4 py-8 sm:px-6">
            <div className="ml-auto h-10 w-2/5 animate-pulse rounded-2xl bg-slate-200/70" />
            <div className="h-28 w-4/5 animate-pulse rounded-2xl bg-white" />
            <div className="ml-auto h-10 w-1/3 animate-pulse rounded-2xl bg-slate-200/70" />
          </div>
        ) : error || !doc ? (
          <div className="mx-auto max-w-md px-4 py-20 text-center">
            <p className="text-sm font-medium text-slate-700">
              {error || "文档不存在"}
            </p>
            <Link
              href="/docs"
              className="mt-4 inline-flex items-center gap-1 rounded-xl bg-emerald-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-600"
            >
              返回文档列表
            </Link>
          </div>
        ) : messages.length === 0 && !ready ? (
          <div className="mx-auto max-w-md px-4 py-20 text-center">
            {doc.status === "error" ? (
              <>
                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-rose-50 text-rose-500">
                  <svg
                    className="size-6"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <path d="M12 8v5m0 3h.01" />
                  </svg>
                </span>
                <p className="mt-4 text-sm font-medium text-slate-700">
                  文档解析失败
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  请返回列表删除后重新上传，或检查文件是否为有效 PDF。
                </p>
              </>
            ) : (
              <>
                <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-amber-50 text-amber-500">
                  <span className="size-5 animate-spin rounded-full border-2 border-amber-200 border-t-amber-500" />
                </span>
                <p className="mt-4 text-sm font-medium text-slate-700">
                  文档解析中
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  正在提取文本、切片并建立索引，通常几秒内完成，页面会自动刷新状态。
                </p>
              </>
            )}
            <Link
              href="/docs"
              className="mt-5 inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition hover:border-emerald-200 hover:text-emerald-600"
            >
              返回文档列表
            </Link>
          </div>
        ) : messages.length === 0 ? (
          <div className="mx-auto flex max-w-md flex-col items-center px-4 py-16 text-center sm:py-20">
            <span className="grid size-14 place-items-center rounded-2xl bg-linear-to-br from-emerald-500 to-teal-600 text-xl font-bold text-white shadow-lg shadow-emerald-500/25">
              文
            </span>
            <h2 className="mt-4 text-lg font-semibold tracking-tight text-slate-900">
              关于这份文档，你想了解什么？
            </h2>
            <p className="mt-1.5 text-sm text-slate-500">
              「{doc.filename}」已解析完成，答案会标注来源页码。
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void send(suggestion)}
                  className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-xs text-slate-600 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-5 px-4 py-6 sm:px-6">
            {messages.map((message, index) =>
              message.role === "user" ? (
                <div
                  key={index}
                  className="animate-fade-up flex justify-end"
                >
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-emerald-600 px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words text-white shadow-sm shadow-emerald-600/20">
                    {message.content}
                  </div>
                </div>
              ) : (
                <div key={index} className="animate-fade-up flex gap-3">
                  <AssistantAvatar />
                  <div className="max-w-[85%] rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3 shadow-sm">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap break-words text-slate-700">
                      {message.content}
                    </p>
                    <Citations citations={message.citations ?? []} />
                  </div>
                </div>
              ),
            )}

            {sending && (
              <div className="flex gap-3">
                <AssistantAvatar />
                <div className="rounded-2xl rounded-tl-md border border-slate-200 bg-white px-4 py-3.5 shadow-sm">
                  <span className="flex items-center gap-1">
                    {[0, 150, 300].map((delay) => (
                      <span
                        key={delay}
                        className="size-1.5 animate-bounce rounded-full bg-slate-300"
                        style={{ animationDelay: `${delay}ms` }}
                      />
                    ))}
                  </span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </main>

      <footer className="shrink-0 border-t border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto max-w-3xl px-4 py-3 sm:px-6">
          {chatError && (
            <div
              role="alert"
              className="mb-2 flex items-start justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-600"
            >
              <span>{chatError}</span>
              <button
                type="button"
                onClick={() => setChatError("")}
                className="shrink-0 text-rose-400 hover:text-rose-600"
              >
                关闭
              </button>
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-sm transition focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-500/10"
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={!canAsk}
              placeholder={
                ready
                  ? "向这份文档提问…"
                  : doc?.status === "error"
                    ? "文档解析失败，无法提问"
                    : "文档解析中，完成后即可提问"
              }
              className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2.5 py-2 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!canAsk || !input.trim()}
              aria-label="发送"
              className="grid size-10 shrink-0 place-items-center rounded-xl bg-emerald-500 text-white transition hover:bg-emerald-600 disabled:bg-slate-100 disabled:text-slate-400"
            >
              {sending ? (
                <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
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
                  <path d="m22 2-7 20-4-9-9-4Z" />
                  <path d="M22 2 11 13" />
                </svg>
              )}
            </button>
          </form>

          <p className="mt-1.5 text-center text-[11px] text-slate-400">
            Enter 发送 · Shift + Enter 换行 · AI 回答仅供参考，请核对引用原文
          </p>
        </div>
      </footer>
    </div>
  );
}
