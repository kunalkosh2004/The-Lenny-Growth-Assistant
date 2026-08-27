"use client";

import type { MessageResponse, Source } from "@/types/api";
import { User, Bot, AlertTriangle, Cpu, Cloud } from "lucide-react";
import SourceCard from "./SourceCard";

const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Local (Ollama)",
  openai: "OpenAI",
  anthropic: "Anthropic",
  google: "Gemini",
};

function ProviderBadge({ provider, model }: { provider: string; model: string }) {
  if (!provider) return null;
  const label = PROVIDER_LABELS[provider.toLowerCase()] ?? provider;
  const isLocal = provider.toLowerCase() === "ollama";
  return (
    <div className="mt-1.5 flex justify-end">
      <span className="inline-flex items-center gap-1 rounded-full border border-line bg-paper px-2 py-0.5 text-[10px] text-neutral-500">
        {isLocal ? <Cpu size={10} /> : <Cloud size={10} />}
        {label}
        {model && <span className="text-neutral-400">· {model}</span>}
      </span>
    </div>
  );
}

export default function ChatMessage({
  message,
  sources,
  groundingStatus,
}: {
  message: MessageResponse;
  sources?: Source[];
  groundingStatus?: string;
}) {
  const isUser = message.role === "user";
  const isError =
    groundingStatus === "error" ||
    message.content.includes("error occurred");

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : ""}`}>
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
          <Bot size={16} />
        </div>
      )}

      <div className={`max-w-[760px] ${isUser ? "order-first" : ""}`}>
        {/* Message bubble */}
        <div
          className={`rounded-md p-4 ${
            isUser
              ? "bg-accent text-white"
              : isError
                ? "border border-red-200 bg-red-50"
                : "border border-line bg-white"
          }`}
        >
          <p
            className={`text-xs font-semibold ${isUser ? "text-white/80" : "text-neutral-500"}`}
          >
            {isUser ? "You" : isError ? "Error" : "Assistant"}
          </p>
          <div
            className={`mt-2 whitespace-pre-wrap text-sm leading-6 ${
              isUser
                ? "text-white"
                : isError
                  ? "text-red-700"
                  : "text-neutral-700"
            }`}
          >
            {message.content}
          </div>
        </div>

        {/* Source citations */}
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {sources.map((source, i) => (
              <SourceCard key={i} source={source} index={i + 1} />
            ))}
          </div>
        )}

        {/* Grounding status */}
        {!isUser && groundingStatus === "no_relevant_sources" && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-warn">
            <AlertTriangle size={14} />
            <span>No relevant transcript sources found</span>
          </div>
        )}

        {/* Provider/model badge */}
        {!isUser && message.metadata && (
          <ProviderBadge
            provider={String(message.metadata.provider || "")}
            model={String(message.metadata.model || "")}
          />
        )}
      </div>

      {isUser && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-white">
          <User size={16} />
        </div>
      )}
    </div>
  );
}
