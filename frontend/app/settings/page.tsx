"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { LlmStatus } from "@/lib/types";
import { Brand } from "@/components/Brand";

export default function SettingsPage() {
  const [status, setStatus] = useState<LlmStatus | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [message, setMessage] = useState("");
  const [messageOk, setMessageOk] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    api
      .getLlmStatus()
      .then(setStatus)
      .catch(() => setMessageOk(false))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setMessage("");
    try {
      const next = await api.saveLlmKey(keyInput.trim());
      setStatus(next);
      setKeyInput("");
      setMessageOk(true);
      setMessage(next.configured ? "已保存，AI 生成模式已启用" : "已清除，回到原文摘录模式");
    } catch (err) {
      setMessageOk(false);
      setMessage(err instanceof ApiError ? err.message : "保存失败，请重试");
    } finally {
      setSaving(false);
    }
  }

  async function handleVerify() {
    setVerifying(true);
    setMessage("");
    try {
      const result = await api.verifyLlmKey(keyInput.trim());
      setMessageOk(result.ok);
      setMessage(result.message);
    } catch (err) {
      setMessageOk(false);
      setMessage(err instanceof ApiError ? err.message : "校验失败，请重试");
    } finally {
      setVerifying(false);
    }
  }

  const modeText =
    status?.mode === "user"
      ? "已启用生成模式（使用你自己的 Key）"
      : status?.mode === "global"
        ? "已启用生成模式（使用平台配置的 Key）"
        : "摘录模式（回答为原文摘录，不消耗 AI 费用）";

  return (
    <div className="min-h-dvh bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
          <Brand />
          <Link
            href="/docs"
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-white"
          >
            返回文档
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        <h1 className="text-2xl font-semibold text-slate-900">AI 设置</h1>
        <p className="mt-2 text-sm text-slate-500">
          填入你自己的 DeepSeek API Key 后，回答将从「原文摘录」升级为「AI 生成」，引用溯源机制不变。
        </p>

        <section className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-medium text-slate-900">DeepSeek API Key</h2>
            <span
              className={`rounded-full px-2.5 py-1 text-xs ${
                status?.configured
                  ? "bg-emerald-50 text-emerald-600"
                  : "bg-slate-100 text-slate-500"
              }`}
            >
              {loading ? "读取中…" : status?.configured ? `已配置（${status.masked}）` : "未配置"}
            </span>
          </div>

          <p className="mt-3 text-sm text-slate-500">当前模式：{loading ? "…" : modeText}</p>

          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="sk-…（粘贴你的 DeepSeek API Key）"
            className="mt-4 w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
          <p className="mt-2 text-xs text-slate-400">
            没有 Key？到{" "}
            <a
              href="https://platform.deepseek.com"
              target="_blank"
              rel="noreferrer"
              className="text-indigo-500 hover:underline"
            >
              platform.deepseek.com
            </a>{" "}
            注册并创建，Key 仅保存在你的账号下，清空输入框保存即视为清除。
          </p>

          <div className="mt-4 flex gap-2">
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? "保存中…" : "保存 Key"}
            </button>
            <button
              onClick={() => void handleVerify()}
              disabled={verifying || (!keyInput.trim() && !status?.configured)}
              className="rounded-xl border border-slate-200 px-4 py-2 text-sm text-slate-600 transition hover:bg-slate-50 disabled:opacity-50"
            >
              {verifying ? "校验中…" : "测试 Key 是否可用"}
            </button>
          </div>

          {message && (
            <p className={`mt-4 text-sm ${messageOk ? "text-emerald-600" : "text-rose-500"}`}>{message}</p>
          )}
        </section>

        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-medium text-slate-900">为什么需要 Key？</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-500">
            <li>· 不配置：回答为文档原文摘录 + 出处标注，完全免费</li>
            <li>· 配置后：AI 基于检索片段生成归纳式回答，费用由你的 Key 承担（一次问答约几分钱）</li>
            <li>· 引用溯源在两种模式下都可用，点击引用即可核对原文</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
