import { clearToken, getToken } from "./auth";
import type {
  AuthResponse,
  CaptchaData,
  ChatMessage,
  ChatResponse,
  DocumentItem,
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
