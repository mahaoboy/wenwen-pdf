"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { getToken, setToken } from "@/lib/auth";
import { Brand } from "@/components/Brand";

type Mode = "login" | "register" | "verify";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [captcha, setCaptcha] = useState<{ captcha_id: string; image: string } | null>(null);
  const [captchaCode, setCaptchaCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (getToken()) router.replace("/docs");
  }, [router]);

  const refreshCaptcha = useCallback(async () => {
    setCaptchaCode("");
    try {
      setCaptcha(await api.getCaptcha());
    } catch {
      setCaptcha(null);
    }
  }, []);

  useEffect(() => {
    if (mode !== "verify") void refreshCaptcha();
  }, [mode, refreshCaptcha]);

  function switchMode(next: Mode) {
    if (next === mode) return;
    setMode(next);
    setError("");
    setNotice("");
    setDevCode(null);
  }

  function handleApiError(err: unknown) {
    const message = err instanceof ApiError ? err.message : "操作失败，请稍后重试";
    setError(message);
    void refreshCaptcha(); // 失败后换一张验证码
    setLoading(false);
    // 登录时发现邮箱未验证 → 引导进入验证视图
    if (err instanceof ApiError && err.status === 403 && message.includes("未验证")) {
      setMode("verify");
      setError("");
      setNotice("该邮箱还未完成验证，请输入邮件中的 6 位验证码。");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        const result = await api.login(email.trim(), password, captcha?.captcha_id ?? "", captchaCode);
        setToken(result.access_token);
        router.replace("/docs");
        return;
      }
      if (mode === "register") {
        const outcome = await api.register(email.trim(), password, captcha?.captcha_id ?? "", captchaCode);
        setDevCode(outcome.dev_code);
        setMode("verify");
        setNotice(
          outcome.smtp_configured
            ? "验证码已发送到你的邮箱，10 分钟内有效。"
            : "SMTP 未配置（本地部署）：验证码如下，直接填入即可。",
        );
        setLoading(false);
        return;
      }
    } catch (err) {
      handleApiError(err);
      return;
    }
  }

  async function handleVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      const result = await api.verifyEmail(email.trim(), code.trim());
      setToken(result.access_token);
      router.replace("/docs");
    } catch (err) {
      handleApiError(err);
    }
  }

  async function handleResend() {
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      const outcome = await api.resendCode(email.trim(), captcha?.captcha_id ?? "", captchaCode);
      setDevCode(outcome.dev_code);
      setNotice(outcome.smtp_configured ? "验证码已重新发送。" : "验证码已重新生成（SMTP 未配置）。");
      await refreshCaptcha();
    } catch (err) {
      handleApiError(err);
      return;
    }
    setLoading(false);
  }

  const isVerify = mode === "verify";

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-paper px-4 py-10">
      <div className="pointer-events-none absolute -top-32 -left-32 size-96 rounded-full bg-accent-wash blur-3xl" />
      <div className="pointer-events-none absolute -right-32 -bottom-32 size-96 rounded-full bg-slate-200/50 blur-3xl" />

      <div className="relative w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Brand />
        </div>

        <div className="rounded-3xl border border-slate-200/80 bg-white/90 p-7 shadow-xl shadow-slate-200/60 backdrop-blur">
          {isVerify ? (
            <>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">验证邮箱</h1>
              <p className="mt-1.5 text-sm text-slate-500">
                向 <span className="font-medium text-slate-700">{email}</span> 发送了 6 位验证码，10 分钟内有效。
              </p>

              {devCode && (
                <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-sm text-amber-700">
                  {notice} 当前验证码：
                  <span className="font-bold tracking-widest text-amber-900">{devCode}</span>
                </div>
              )}
              {!devCode && notice && (
                <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2.5 text-sm text-emerald-700">
                  {notice}
                </p>
              )}

              <form onSubmit={(e) => void handleVerify(e)} className="mt-5 space-y-4">
                <div>
                  <label htmlFor="code" className="mb-1.5 block text-sm font-medium text-slate-700">
                    邮箱验证码
                  </label>
                  <input
                    id="code"
                    inputMode="numeric"
                    required
                    maxLength={6}
                    value={code}
                    onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                    placeholder="6 位数字"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-center text-lg font-semibold tracking-[0.5em] text-slate-900 outline-none transition placeholder:font-normal placeholder:tracking-normal placeholder:text-slate-400 focus:border-accent focus:ring-4 focus:ring-accent/10"
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
                  完成验证并进入
                </button>
              </form>

              <div className="mt-4 flex items-center justify-between text-xs">
                <button
                  type="button"
                  onClick={() => void handleResend()}
                  disabled={loading}
                  className="text-accent transition hover:underline disabled:opacity-50"
                >
                  没收到？重发验证码
                </button>
                <button
                  type="button"
                  onClick={() => switchMode("register")}
                  className="text-slate-400 transition hover:text-slate-600"
                >
                  返回注册
                </button>
              </div>
            </>
          ) : (
            <>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">
                {mode === "login" ? "欢迎回来" : "创建账号"}
              </h1>
              <p className="mt-1.5 text-sm text-slate-500">
                {mode === "login"
                  ? "登录后继续与你的 PDF 文档对话。"
                  : "注册需要邮箱验证，验证通过才能登录。"}
              </p>

              <div className="mt-6 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1">
                {(["login", "register"] as const).map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => switchMode(item)}
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                      mode === item ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {item === "login" ? "登录" : "注册"}
                  </button>
                ))}
              </div>

              <form onSubmit={(e) => void handleSubmit(e)} className="mt-6 space-y-4">
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
                  <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-slate-700">
                    密码
                  </label>
                  <div className="flex items-stretch gap-2">
                    <input
                      id="password"
                      type="password"
                      required
                      minLength={6}
                      autoComplete={mode === "login" ? "current-password" : "new-password"}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      placeholder="至少 6 位"
                      className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-accent focus:ring-4 focus:ring-accent/10"
                    />
                    {mode === "login" && (
                      <a
                        href="/reset"
                        className="shrink-0 self-center rounded-xl px-3 text-sm font-medium text-accent transition hover:bg-accent/5 hover:underline"
                      >
                        忘记密码？
                      </a>
                    )}
                  </div>
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
                  {loading ? "请稍候…" : mode === "login" ? "登录" : "注册并获取验证码"}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          免费版可上传 3 份文档，累计提问 20 次
        </p>
        <p className="mt-3 text-center text-xs">
          <a href="/" className="text-slate-400 transition hover:text-accent">
            ← 返回文问首页
          </a>
        </p>
      </div>
    </div>
  );
}
