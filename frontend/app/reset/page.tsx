"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { Brand } from "@/components/Brand";

type Phase = "request" | "reset";

function ResetPasswordContent() {
  const router = useRouter();
  const params = useSearchParams();
  const tokenParam = params.get("token");

  const [phase, setPhase] = useState<Phase>(tokenParam ? "reset" : "request");
  const [email, setEmail] = useState("");
  const [captcha, setCaptcha] = useState<{ captcha_id: string; image: string } | null>(null);
  const [captchaCode, setCaptchaCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const refreshCaptcha = useCallback(async () => {
    setCaptchaCode("");
    try {
      setCaptcha(await api.getCaptcha());
    } catch {
      setCaptcha(null);
    }
  }, []);

  useEffect(() => {
    if (phase === "request") void refreshCaptcha();
  }, [phase, refreshCaptcha]);

  function handleApiError(err: unknown) {
    const message = err instanceof ApiError ? err.message : "操作失败，请稍后重试";
    setError(message);
    if (phase === "request") void refreshCaptcha();
    setLoading(false);
  }

  async function handleRequestReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const result = await api.forgotPassword(email.trim(), captcha?.captcha_id ?? "", captchaCode);
      setDevResetUrl(result.dev_reset_url);
      setNotice(
        result.smtp_configured
          ? "重置链接已发送到你的邮箱，15 分钟内有效。"
          : "SMTP 未配置（本地部署）：重置链接如下，点击即可重置密码。",
      );
      setLoading(false);
    } catch (err) {
      handleApiError(err);
    }
  }

  async function handleResetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      const result = await api.resetPassword(tokenParam ?? "", newPassword);
      setToken(result.access_token);
      router.replace("/docs");
    } catch (err) {
      handleApiError(err);
    }
  }

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-paper px-4 py-10">
      <div className="pointer-events-none absolute -top-32 -left-32 size-96 rounded-full bg-accent-wash blur-3xl" />
      <div className="pointer-events-none absolute -right-32 -bottom-32 size-96 rounded-full bg-slate-200/50 blur-3xl" />

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Brand />
        </div>

        <div className="rounded-3xl border border-slate-200/80 bg-white/90 p-7 shadow-xl shadow-slate-200/60 backdrop-blur">
          {phase === "request" ? (
            <>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">忘记密码</h1>
              <p className="mt-1.5 text-sm text-slate-500">
                输入注册邮箱，我们会发送密码重置链接到你的邮箱。
              </p>

              {notice && (
                <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                  {notice}
                </p>
              )}
              {devResetUrl && (
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm">
                  <p className="text-amber-700">当前重置链接：</p>
                  <a
                    href={devResetUrl}
                    className="mt-1 block break-all font-medium text-amber-900 underline"
                  >
                    {devResetUrl}
                  </a>
                </div>
              )}

              <form onSubmit={(e) => void handleRequestReset(e)} className="mt-5 space-y-4">
                <div>
                  <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-slate-700">
                    邮箱
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-4 focus:ring-accent/10"
                  />
                </div>

                <div>
                  <label htmlFor="captcha" className="mb-1.5 block text-sm font-medium text-slate-700">
                    图片验证码
                  </label>
                  <div className="flex items-stretch gap-2">
                    <input
                      id="captcha"
                      required
                      maxLength={4}
                      autoComplete="off"
                      value={captchaCode}
                      onChange={(event) => setCaptchaCode(event.target.value.toUpperCase())}
                      placeholder="输入右侧字符"
                      className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm uppercase tracking-widest text-slate-900 outline-none transition placeholder:tracking-normal placeholder:text-slate-400 focus:border-accent focus:ring-4 focus:ring-accent/10"
                    />
                    <button
                      type="button"
                      onClick={() => void refreshCaptcha()}
                      title="点击刷新验证码"
                      className="shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-white transition hover:border-accent"
                    >
                      {captcha ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={captcha.image} alt="图片验证码" className="h-full w-32 object-cover" />
                      ) : (
                        <span className="grid h-full w-32 place-items-center text-xs text-slate-400">加载中…</span>
                      )}
                    </button>
                  </div>
                </div>

                {error && (
                  <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-600">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading || !captcha}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-accent/25 transition hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
                  发送重置链接
                </button>
              </form>
            </>
          ) : (
            <>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">设置新密码</h1>
              <p className="mt-1.5 text-sm text-slate-500">
                请输入你的新密码，重置后即可使用新密码登录。
              </p>

              <form onSubmit={(e) => void handleResetPassword(e)} className="mt-6 space-y-4">
                <div>
                  <label htmlFor="new-password" className="mb-1.5 block text-sm font-medium text-slate-700">
                    新密码
                  </label>
                  <input
                    id="new-password"
                    type="password"
                    required
                    minLength={6}
                    autoComplete="new-password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="至少 6 位"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-4 focus:ring-accent/10"
                  />
                </div>

                {error && (
                  <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-600">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-accent/25 transition hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading && <span className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
                  重置密码并登录
                </button>
              </form>

              <div className="mt-4 text-center text-xs">
                <a href="/reset" className="text-slate-400 transition hover:text-accent">
                  ← 换个邮箱重新申请
                </a>
              </div>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs">
          <a href="/login" className="text-slate-400 transition hover:text-accent">
            ← 返回登录
          </a>
        </p>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  );
}