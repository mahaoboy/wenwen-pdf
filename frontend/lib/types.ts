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
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
}
