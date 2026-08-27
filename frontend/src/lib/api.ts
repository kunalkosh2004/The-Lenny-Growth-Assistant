import { apiBaseUrl } from "./config";
import type {
  Artifact,
  ArtifactListResponse,
  ArtifactStored,
  ChatApiResponse,
  HealthResponse,
  KnowledgeStatus,
  OllamaModelsResponse,
  ProvidersResponse,
  SessionDetail,
  SessionSummary,
  Ship30Response,
} from "@/types/api";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const url = `${apiBaseUrl}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json();
}

// --- Health ---

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getReadiness(): Promise<{ status: string }> {
  return request<{ status: string }>("/health/ready");
}

// --- Sessions ---

export async function createSession(
  title?: string,
): Promise<SessionSummary> {
  return request<SessionSummary>("/api/sessions", {
    method: "POST",
    body: JSON.stringify({ title: title || null }),
  });
}

export async function listSessions(): Promise<SessionSummary[]> {
  return request<SessionSummary[]>("/api/sessions");
}

export async function getSession(
  sessionId: string,
): Promise<SessionDetail> {
  return request<SessionDetail>(`/api/sessions/${sessionId}`);
}

export async function deleteSession(
  sessionId: string,
): Promise<void> {
  await request(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

export async function updateSession(
  sessionId: string,
  title: string,
): Promise<SessionSummary> {
  return request<SessionSummary>(`/api/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

// --- Chat ---

export async function sendChat(
  sessionId: string,
  message: string,
  topK: number = 6,
): Promise<ChatApiResponse> {
  return request<ChatApiResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      message,
      top_k: topK,
    }),
  });
}

// --- Providers ---

export async function listProviders(): Promise<ProvidersResponse> {
  return request<ProvidersResponse>("/api/providers");
}

export async function listOllamaModels(): Promise<OllamaModelsResponse> {
  return request<OllamaModelsResponse>("/api/providers/models");
}

export async function selectProvider(
  provider: string,
  model?: string,
): Promise<{ active_provider: string; active_model: string; info: Record<string, unknown> }> {
  return request("/api/providers/select", {
    method: "POST",
    body: JSON.stringify({ provider, model: model ?? null }),
  });
}

// --- Knowledge ---

export async function getKnowledgeStatus(): Promise<KnowledgeStatus> {
  return request<KnowledgeStatus>("/api/knowledge/status");
}

// --- Artifacts ---

export async function generateArtifact(params: {
  sessionId: string;
  artifactType: "markdown" | "html";
  request: string;
  topK?: number;
}): Promise<Artifact> {
  return request<Artifact>("/api/artifacts/generate", {
    method: "POST",
    body: JSON.stringify({
      session_id: params.sessionId,
      artifact_type: params.artifactType,
      request: params.request,
      top_k: params.topK ?? 10,
    }),
  });
}

export async function getArtifact(
  artifactId: string,
): Promise<ArtifactStored> {
  return request<ArtifactStored>(`/api/artifacts/${artifactId}`);
}

export async function listSessionArtifacts(
  sessionId: string,
): Promise<ArtifactListResponse> {
  return request<ArtifactListResponse>(
    `/api/artifacts/session/${sessionId}`,
  );
}

// --- Ship 30 Skill ---

export async function generateShip30(params: {
  topic: string;
  sessionId?: string;
  topK?: number;
  targetWords?: number;
}): Promise<Ship30Response> {
  return request<Ship30Response>("/api/skills/ship30", {
    method: "POST",
    body: JSON.stringify({
      topic: params.topic,
      session_id: params.sessionId ?? null,
      top_k: params.topK ?? 10,
      target_words: params.targetWords ?? 1250,
    }),
  });
}
