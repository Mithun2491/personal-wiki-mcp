export type ApiErrorCode =
  | "invalid_request"
  | "not_found"
  | "unauthorized"
  | "config"
  | "unreachable"
  | "timeout"
  | "backend"
  | "internal";

export interface ApiErrorBody {
  error: {
    code: ApiErrorCode;
    message: string;
  };
}

export type ConnectionMode = "local" | "remote";

export interface StatusPayload {
  connected: boolean;
  configured: boolean;
  mode: ConnectionMode | null;
  url: string | null;
  server: { name: string | null; version: string | null } | null;
  tools: string[];
  error: { code: ApiErrorCode; message: string } | null;
}

export interface WikiEntry {
  name: string;
  path: string | null;
  description: string | null;
  status: string;
  is_hub: boolean;
}

export interface WikiListPayload {
  default: string | null;
  count: number;
  truncated: boolean;
  wikis: WikiEntry[];
}

export interface SearchMatch {
  path: string;
  line: number;
  snippet: string;
}

export interface SearchPayload {
  query: string;
  wiki: string;
  files_scanned: number;
  match_count: number;
  max_results: number;
  truncated: boolean;
  matches: SearchMatch[];
}

export interface ArticlePayload {
  path: string;
  markdown: string;
}

export interface IndexPayload {
  wiki: string;
  markdown: string;
}
