"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Loader2, MessageSquarePlus } from "lucide-react";
import {
  createSession,
  listSessions,
  listProviders,
  listOllamaModels,
  selectProvider,
} from "@/lib/api";
import type {
  OllamaModel,
  ProviderInfo,
  SessionSummary,
} from "@/types/api";

export default function SessionSidebar({
  activeSessionId,
  onSelectSession,
  onNewChat,
}: {
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
}) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [activeProvider, setActiveProvider] = useState("ollama");
  const [activeModel, setActiveModel] = useState("");
  const [loading, setLoading] = useState(true);

  // Ollama model list
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [switching, setSwitching] = useState(false);

  const refresh = async () => {
    try {
      const [sess, prov] = await Promise.all([
        listSessions(),
        listProviders(),
      ]);
      setSessions(sess);
      setProviders(prov.providers || []);
      setActiveProvider(prov.active_provider || "ollama");
      setActiveModel(prov.active_model || "");
    } catch {
      // Backend may be unavailable.
    } finally {
      setLoading(false);
    }
  };

  // Fetch Ollama models when provider is ollama
  const refreshModels = async () => {
    try {
      const data = await listOllamaModels();
      setOllamaModels(data.generation_models || []);
    } catch {
      setOllamaModels([]);
    }
  };

  useEffect(() => {
    refresh();
    if (activeProvider === "ollama") {
      refreshModels();
    }
  }, []);

  useEffect(() => {
    if (activeProvider === "ollama") {
      refreshModels();
    }
  }, [activeProvider]);

  const handleNewChat = async () => {
    try {
      const session = await createSession();
      setSessions((prev) => [session, ...prev]);
      onSelectSession(session.id);
      onNewChat();
    } catch {
      // ignore
    }
  };

  const handleModelSwitch = async (modelName: string) => {
    setSwitching(true);
    setShowModelDropdown(false);
    try {
      const result = await selectProvider(activeProvider, modelName);
      setActiveModel(result.active_model);
      // Re-fetch provider status
      const prov = await listProviders();
      setProviders(prov.providers || []);
      setActiveProvider(prov.active_provider || "ollama");
    } catch {
      // ignore
    } finally {
      setSwitching(false);
    }
  };

  const activeProv = providers.find((p) => p.provider === activeProvider);

  return (
    <aside className="flex h-full flex-col border-b border-line bg-white px-5 py-5 lg:border-b-0 lg:border-r">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-accent">
            Internal AI
          </p>
          <h1 className="mt-1 text-xl font-semibold">Lenny Growth Assistant</h1>
        </div>
        <button
          onClick={handleNewChat}
          className="grid h-10 w-10 place-items-center rounded-md border border-line bg-paper hover:bg-neutral-100"
          aria-label="Start new chat"
        >
          <MessageSquarePlus size={19} />
        </button>
      </div>

      {/* Provider status with model dropdown */}
      <div className="mt-6 rounded-md border border-line bg-paper p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Model Provider
        </p>
        <p className="mt-2 text-sm font-medium capitalize">{activeProvider}</p>

        {/* Model selector dropdown */}
        <div className="relative mt-2">
          <button
            onClick={() => {
              if (!switching && ollamaModels.length > 0) {
                setShowModelDropdown(!showModelDropdown);
              }
            }}
            disabled={switching || ollamaModels.length === 0}
            className="flex w-full items-center justify-between gap-2 rounded-md border border-line bg-white px-3 py-2 text-left text-xs font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            {switching ? (
              <span className="flex items-center gap-2">
                <Loader2 size={12} className="animate-spin" />
                Switching...
              </span>
            ) : (
              <span className="truncate">
                {activeModel || "No model selected"}
              </span>
            )}
            {ollamaModels.length > 0 && !switching && (
              <ChevronDown
                size={14}
                className={`shrink-0 text-neutral-400 transition-transform ${
                  showModelDropdown ? "rotate-180" : ""
                }`}
              />
            )}
          </button>

          {showModelDropdown && ollamaModels.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-[260px] overflow-y-auto rounded-md border border-line bg-white shadow-lg">
              {ollamaModels.map((model) => (
                <button
                  key={model.name}
                  onClick={() => handleModelSwitch(model.name)}
                  className={`flex w-full flex-col px-3 py-2 text-left text-xs hover:bg-accent/5 ${
                    model.name === activeModel ? "bg-accent/10 font-medium" : ""
                  }`}
                >
                  <span className="truncate font-medium text-neutral-800">
                    {model.name}
                  </span>
                  <span className="mt-0.5 text-[10px] text-neutral-400">
                    {model.parameter_size} · {model.family} · ctx {model.context_length.toLocaleString()}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="mt-2 flex items-center gap-1.5">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              activeProv?.available ? "bg-green-500" : "bg-red-400"
            }`}
          />
          <span className="text-xs text-neutral-500">
            {activeProv?.status || "unknown"}
          </span>
        </div>
      </div>

      {/* Session list */}
      <nav className="mt-6 flex-1 space-y-1 overflow-y-auto" aria-label="Chat sessions">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Chats
        </p>
        {loading && (
          <p className="text-sm text-neutral-400">Loading...</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className="text-sm text-neutral-400">No chats yet</p>
        )}
        {sessions.map((session) => (
          <div key={session.id} className="group flex items-center gap-1">
            <button
              onClick={() => onSelectSession(session.id)}
              className={`flex-1 truncate rounded-md px-3 py-2 text-left text-sm ${
                session.id === activeSessionId
                  ? "bg-accent/10 font-medium text-accent"
                  : "hover:bg-paper text-neutral-700"
              }`}
            >
              {session.title || "New chat"}
              {session.message_count > 0 && (
                <span className="ml-1 text-xs text-neutral-400">
                  ({session.message_count})
                </span>
              )}
            </button>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="mt-4 border-t border-line pt-3">
        <p className="text-[10px] text-neutral-400">
          Powered by Lenny's Podcast transcripts
        </p>
      </div>
    </aside>
  );
}
