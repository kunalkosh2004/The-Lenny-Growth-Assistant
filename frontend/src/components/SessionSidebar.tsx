"use client";

import { useEffect, useState } from "react";
import {
  MessageSquarePlus,
  Trash2,
} from "lucide-react";
import { createSession, listSessions, listProviders } from "@/lib/api";
import type { ProviderInfo, SessionSummary } from "@/types/api";

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

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 15000);
    return () => clearInterval(interval);
  }, []);

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

      {/* Provider status */}
      <div className="mt-6 rounded-md border border-line bg-paper p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Model Provider
        </p>
        <p className="mt-2 text-sm font-medium capitalize">{activeProvider}</p>
        <p className="mt-0.5 truncate text-xs text-neutral-600">{activeModel}</p>
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
