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
  summary?: string;
  suggestions?: string[];
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

export interface ForgotPasswordOutcome {
  email: string;
  smtp_configured: boolean;
  dev_reset_url: string | null;
}

export interface AdminStats {
  users_total: number;
  users_verified: number;
  docs_total: number;
  questions_total: number;
  tokens_prompt: number;
  tokens_completion: number;
  visits_24h: number;
  chats_24h: number;
  registers_24h: number;
  recent_attacks: Array<{ ts: string; type: string; ip: string; meta: string }>;
}
