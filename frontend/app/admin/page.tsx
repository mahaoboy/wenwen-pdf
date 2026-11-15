"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Brand } from "@/components/Brand";
import type { AdminStats } from "@/lib/types";

const KEY_STORAGE = "wenwen_admin_key";

export default function AdminPage() {
  const [key, setKey] = useState("");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (adminKey: string) => {
    setLoading(true);
    try {
      setStats(await api.getAdminStats(adminKey));
      setError("");
    } catch (err) {
      setStats(null);
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem(KEY_STORAGE);
    if (saved) {
      setKey(saved);
      void load(saved);
    }
  }, [load]);

  // 密钥保存后每 30 秒自动刷新
  useEffect(() => {
    if (!stats) return;
    const timer = setInterval(() => void load(key), 30000);
    return () => clearInterval(timer);
  }, [key, stats, load]);

  function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!key.trim()) return;
    localStorage.setItem(KEY_STORAGE, key.trim());
    void load(key.trim());
  }

  const cards: Array<[string, string | number]> = stats
    ? [
        ["注册用户", `${stats.users_total}（已验证 ${stats.users_verified}）`],
        ["文档总数", stats.docs_total],
        ["提问总数", stats.questions_total],
        ["24h 提问", stats.chats_24h],
        ["24h 访问 IP", stats.visits_24h],
        ["24h 注册", stats.registers_24h],
        ["Token 输入", stats.tokens_prompt.toLocaleString()],
        ["Token 输出", stats.tokens_completion.toLocaleString()],
      ]
    : [];

  return (
    <div className="min-h-dvh bg-paper">
      <header className="sticky top-0 z-10 border-b border-slate-200/80 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-4xl items-center justify-between px-4 sm:px-6">
          <Brand href="/docs" />
          <span className="rounded-full bg-ink px-3 py-1 text-xs font-medium text-white">内部监控</span>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <h1 className="text-2xl font-semibold text-slate-900">运行监控</h1>
        <p className="mt-1 text-sm text-slate-500">
          注册、文档、提问与模型用量聚合；攻击事件触发时告警邮件已发往管理员邮箱。
        </p>

        <form onSubmit={handleSave} className="mt-6 flex gap-2">
          <input
            type="password"
            required
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="ADMIN_KEY（见服务器 .env）"
            className="flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-accent focus:ring-4 focus:ring-accent/10"
          />
          <button
            type="submit"
            className="rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-deep"
          >
            加载
          </button>
        </form>

        {error && (
          <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-600">
            {error}
          </p>
        )}

        {stats && (
          <>
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {cards.map(([label, value]) => (
                <div key={label} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                  <div className="text-lg font-semibold text-slate-900">{value}</div>
                  <div className="mt-0.5 text-xs text-slate-400">{label}</div>
                </div>
              ))}
            </div>

            <h2 className="mt-8 text-base font-medium text-slate-900">攻击事件（最近 20 条）</h2>
            {stats.recent_attacks.length === 0 ? (
              <p className="mt-3 rounded-xl border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-400">
                暂无攻击事件——阈值触发时会自动发告警邮件。
              </p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white text-sm">
                {stats.recent_attacks.map((attack, index) => (
                  <li key={index} className="flex items-center justify-between gap-3 px-4 py-2.5">
                    <span className="font-medium text-rose-600">{attack.type}</span>
                    <span className="text-slate-500">{attack.ip}</span>
                    <span className="text-xs text-slate-400">{attack.ts.slice(0, 19)}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </main>
    </div>
  );
}
