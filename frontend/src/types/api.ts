export type HealthResponse = {
  status: string;
  app_env: string;
};

export type SessionSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type MessageResponse = {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type SessionDetail = SessionSummary & {
  messages: MessageResponse[];
};

export type Source = {
  title: string;
  guest: string;
  publish_date: string;
  youtube_url: string;
  source_path: string;
  relevance?: string;
};

export type ChatApiResponse = {
  message: MessageResponse;
  sources: Source[];
  model: string;
  provider: string;
  usage: Record<string, number>;
  grounding_status: string;
};

export type ProviderInfo = {
  provider: string;
  model: string;
  base_url?: string;
  available: boolean;
  status: string;
  error?: string;
};

export type ProvidersResponse = {
  providers: ProviderInfo[];
  active_provider: string;
  active_model: string;
};

export type Artifact = {
  artifact_id: string;
  type: "markdown" | "html";
  title: string;
  content: string;
  sources: Source[];
  model: string;
  provider: string;
};

export type ArtifactStored = {
  id: string;
  session_id: string;
  type: string;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ArtifactListResponse = {
  artifacts: { id: string; type: string; title: string; created_at: string }[];
  count: number;
};

export type KnowledgeStatus = {
  episodes_discovered_on_disk: number;
  episodes_indexed: number;
  chunks_indexed: number;
  episodes_missing_title_or_guest: number;
  embedding_model: string | null;
  source_directory: string;
};

export type Ship30Response = {
  status: string;
  content: string;
  word_count: number;
  sources: Source[];
  model: string;
  provider: string;
  error?: string;
};

export type OllamaModel = {
  name: string;
  size?: number;
  parameter_size?: string;
  family: string;
  context_length: number;
  is_embedding?: boolean;
  provider?: string;
  available?: boolean;
};

export type OllamaModelsResponse = {
  generation_models: OllamaModel[];
  embedding_models: OllamaModel[];
  cloud_models: OllamaModel[];
};
