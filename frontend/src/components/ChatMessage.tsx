"use client";

import type { MessageResponse, Source } from "@/types/api";
import { User, Bot, AlertTriangle } from "lucide-react";
import SourceCard from "./SourceCard";

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

        {/* Model info */}
        {!isUser && message.metadata && (
          <p className="mt-1 text-[10px] text-neutral-400">
            {String(message.metadata.provider || "")}/{String(message.metadata.model || "")}
          </p>
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
