export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export type DocumentStatus = "pending" | "parsing" | "ready" | "error";

export interface DocumentItem {
  id: number;
  filename: string;
  status: DocumentStatus;
  page_count: number;
  chunk_count: number;
}

export interface Citation {
  chunk_id: string;
  page: number;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  session_id: string;
  mode: "llm" | "extractive" | string;
}

export interface ChatMessage {
  session_id?: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
}

export interface QuotaInfo {
  plan: string;
  doc_used: number;
  doc_limit: number;
  question_used: number;
  question_limit: number;
}

export interface LlmStatus {
  configured: boolean;
  masked: string | null;
  mode: "user" | "global" | "extractive" | string;
}

export interface VerifyResult {
  ok: boolean;
  message: string;
}

export interface CaptchaData {
  captcha_id: string;
  image: string;
}

export interface RegisterOutcome {
  email: string;
  verification_required: boolean;
  smtp_configured: boolean;
  dev_code: string | null;
}
