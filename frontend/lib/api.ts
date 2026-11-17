import { clearToken, getToken } from "./auth";
import type {
  AdminStats,
  AuthResponse,
  CaptchaData,
  Citation,
  ChatMessage,
  ChatResponse,
  DocumentItem,
  ForgotPasswordOutcome,
  LlmStatus,
  QuotaInfo,
  RegisterOutcome,
  VerifyResult,
} from "./types";

// 同源部署（nginx 统一入口）：构建时设 NEXT_PUBLIC_API_BASE="" → 走相对路径 /api
// 本地开发不设置 → 默认 http://localhost:8000
export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function extractErrorMessage(status: number, body: unknown): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return String(item);
        })
        .filter(Boolean);
      if (messages.length > 0) return messages.join("；");
    }
  }
  if (typeof body === "string" && body.trim()) return body.trim();
  return `请求失败（HTTP ${status}）`;
}

interface RequestOptions {
  redirectOn401?: boolean;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "网络连接失败，请确认后端服务已启动");
  }

  if (response.status === 401 && options.redirectOn401 !== false) {
    clearToken();
    if (
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login")
    ) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "登录已过期，请重新登录");
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      extractErrorMessage(response.status, body),
    );
  }

  return body as T;
}

export const api = {
  getCaptcha(): Promise<CaptchaData> {
    return request<CaptchaData>("/api/auth/captcha", {}, { redirectOn401: false });
  },

  register(
    email: string,
    password: string,
    captchaId: string,
    captchaCode: string,
  ): Promise<RegisterOutcome> {
    return request<RegisterOutcome>(
      "/api/auth/register",
      {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          captcha_id: captchaId,
          captcha_code: captchaCode,
        }),
      },
      { redirectOn401: false },
    );
  },

  verifyEmail(email: string, code: string): Promise<AuthResponse> {
    return request<AuthResponse>(
      "/api/auth/verify-email",
      { method: "POST", body: JSON.stringify({ email, code }) },
      { redirectOn401: false },
    );
  },

  resendCode(email: string, captchaId: string, captchaCode: string): Promise<RegisterOutcome> {
    return request<RegisterOutcome>(
      "/api/auth/resend",
      {
        method: "POST",
        body: JSON.stringify({
          email,
          code: "",
          captcha_id: captchaId,
          captcha_code: captchaCode,
        }),
      },
      { redirectOn401: false },
    );
  },

  forgotPassword(
    email: string,
    captchaId: string,
    captchaCode: string,
  ): Promise<ForgotPasswordOutcome> {
    return request<ForgotPasswordOutcome>(
      "/api/auth/forgot-password",
      {
        method: "POST",
        body: JSON.stringify({ email, captcha_id: captchaId, captcha_code: captchaCode }),
      },
      { redirectOn401: false },
    );
  },

  resetPassword(token: string, newPassword: string): Promise<AuthResponse> {
    return request<AuthResponse>(
      "/api/auth/reset-password",
      { method: "POST", body: JSON.stringify({ token, new_password: newPassword }) },
      { redirectOn401: false },
    );
  },

  login(email: string, password: string, captchaId: string, captchaCode: string): Promise<AuthResponse> {
    return request<AuthResponse>(
      "/api/auth/login",
      {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          captcha_id: captchaId,
          captcha_code: captchaCode,
        }),
      },
      { redirectOn401: false },
    );
  },

  listDocuments(): Promise<DocumentItem[]> {
    return request<DocumentItem[]>("/api/documents");
  },

  uploadDocument(file: File): Promise<DocumentItem> {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentItem>("/api/documents/upload", {
      method: "POST",
      body: form,
    });
  },

  deleteDocument(docId: number): Promise<void> {
    return request<void>(`/api/documents/${docId}`, { method: "DELETE" });
  },

  chat(
    docId: number,
    question: string,
    sessionId?: string | null,
  ): Promise<ChatResponse> {
    return request<ChatResponse>("/api/chat/ask", {
      method: "POST",
      body: JSON.stringify({
        document_id: docId,
        question,
        session_id: sessionId || null,
      }),
    });
  },

  listMessages(docId: number, sessionId?: string | null): Promise<ChatMessage[]> {
    const params = new URLSearchParams({ document_id: String(docId) });
    if (sessionId) params.set("session_id", sessionId);
    return request<ChatMessage[]>(`/api/chat/history?${params.toString()}`);
  },

  getQuota(): Promise<QuotaInfo> {
    return request<QuotaInfo>("/api/billing/quota");
  },

  async chatStream(
    docId: number,
    question: string,
    sessionId: string | null,
    onDelta: (text: string) => void,
  ): Promise<{ citations: Citation[]; session_id: string; mode: string; answer: string }> {
    const token = getToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const resp = await fetch(`${API_BASE}/api/chat/documents/${docId}/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        document_id: docId,
        question,
        session_id: sessionId || null,
      }),
    });

    if (!resp.ok) {
      let detail = `请求失败（HTTP ${resp.status}）`;
      try {
        const body = await resp.json();
        if (typeof body.detail === "string") detail = body.detail;
      } catch {
        /* 保留默认信息 */
      }
      throw new ApiError(resp.status, detail);
    }
    if (!resp.body) throw new ApiError(0, "浏览器不支持流式响应");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    let citations: Citation[] = [];
    let currentSession = sessionId || "";
    let mode = "llm";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        const event = JSON.parse(part.slice(6));
        if (event.type === "delta") {
          answer += event.text;
          onDelta(event.text);
        } else if (event.type === "done") {
          citations = event.citations ?? [];
          currentSession = event.session_id;
          mode = event.mode;
        } else if (event.type === "error") {
          throw new ApiError(500, event.message ?? "生成中断");
        }
      }
    }
    return { citations, session_id: currentSession, mode, answer };
  },

  reparseDocument(docId: number): Promise<{ id: number; status: string }> {
    return request<{ id: number; status: string }>(
      `/api/documents/${docId}/reparse`,
      { method: "POST" },
    );
  },

  recordVisit(): Promise<{ ok: boolean }> {
    return request<{ ok: boolean }>("/api/metrics/visit", { method: "POST" }, { redirectOn401: false });
  },

  getAdminStats(key: string): Promise<AdminStats> {
    return request<AdminStats>(
      "/api/admin/stats",
      { headers: { "X-Admin-Key": key } },
      { redirectOn401: false },
    );
  },

  getLlmStatus(): Promise<LlmStatus> {
    return request<LlmStatus>("/api/settings/llm");
  },

  saveLlmKey(key: string): Promise<LlmStatus> {
    return request<LlmStatus>("/api/settings/llm", {
      method: "PUT",
      body: JSON.stringify({ deepseek_api_key: key }),
    });
  },

  verifyLlmKey(key: string): Promise<VerifyResult> {
    return request<VerifyResult>("/api/settings/llm/verify", {
      method: "POST",
      body: JSON.stringify({ deepseek_api_key: key }),
    });
  },
};
