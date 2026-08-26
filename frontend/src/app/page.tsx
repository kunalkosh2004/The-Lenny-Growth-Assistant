"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Loader2, Sparkles } from "lucide-react";
import SessionSidebar from "@/components/SessionSidebar";
import ChatMessage from "@/components/ChatMessage";
import ArtifactViewer from "@/components/ArtifactViewer";
import {
  createSession,
  getSession,
  sendChat,
  updateSession,
  generateArtifact,
} from "@/lib/api";
import type {
  ArtifactStored,
  ChatApiResponse,
  MessageResponse,
  Source,
} from "@/types/api";

type DisplayMessage = MessageResponse & {
  sources?: Source[];
  groundingStatus?: string;
};

export default function Home() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [activeArtifact, setActiveArtifact] = useState<ArtifactStored | null>(
    null,
  );
  const [showArtifacts, setShowArtifacts] = useState(false);
  const [artifactRequest, setArtifactRequest] = useState("");
  const [artifactType, setArtifactType] = useState<"markdown" | "html">(
    "markdown",
  );
  const [generatingArtifact, setGeneratingArtifact] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Load messages when session changes.
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    getSession(activeSessionId)
      .then((detail) => {
        const display: DisplayMessage[] = detail.messages.map((m) => ({
          ...m,
          sources: (m.metadata?.sources as Source[]) || [],
          groundingStatus: (m.metadata?.grounding_status as string) || undefined,
        }));
        setMessages(display);
      })
      .catch(() => setMessages([]));
  }, [activeSessionId]);

  const handleSend = async () => {
    if (!input.trim() || !activeSessionId || sending) return;
    const userMsg = input.trim();
    setInput("");
    setSending(true);

    // Check if this is the first message — if so, auto-title the session.
    const isFirstMessage = messages.length === 0;

    // Add user message immediately.
    const tempUserMsg: DisplayMessage = {
      id: `temp-${Date.now()}`,
      session_id: activeSessionId,
      role: "user",
      content: userMsg,
      metadata: {},
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    // Auto-title the session with the first message.
    if (isFirstMessage) {
      const title = userMsg.length > 80 ? userMsg.slice(0, 80) + "..." : userMsg;
      updateSession(activeSessionId, title).catch(() => {});
    }

    try {
      const response: ChatApiResponse = await sendChat(
        activeSessionId,
        userMsg,
      );
      // Replace temp message with real messages.
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempUserMsg.id),
        {
          ...tempUserMsg,
          id: `user-${response.message.id}`,
        },
        {
          ...response.message,
          sources: response.sources,
          groundingStatus: response.grounding_status,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempUserMsg.id),
        tempUserMsg,
        {
          id: `error-${Date.now()}`,
          session_id: activeSessionId,
          role: "assistant",
          content:
            "Failed to get a response. Please check that the backend is running and the LLM provider is available.",
          metadata: {},
          created_at: new Date().toISOString(),
          groundingStatus: "error",
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleGenerateArtifact = async () => {
    if (!artifactRequest.trim() || !activeSessionId) return;
    setGeneratingArtifact(true);
    try {
      const result = await generateArtifact({
        sessionId: activeSessionId,
        artifactType,
        request: artifactRequest.trim(),
      });
      // Fetch the stored artifact for viewing.
      const stored = await import("@/lib/api").then((m) =>
        m.getArtifact(result.artifact_id),
      );
      setActiveArtifact(stored);
      setShowArtifacts(true);
      setArtifactRequest("");
    } catch {
      // ignore
    } finally {
      setGeneratingArtifact(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveArtifact(null);
    setShowArtifacts(false);
  };

  /** Create a new session and immediately send the given message. */
  const handleSuggestion = async (question: string) => {
    try {
      const session = await createSession();
      setActiveSessionId(session.id);
      // Small delay so the session state settles before sending.
      setInput(question);
      // Send after a tick so activeSessionId is set.
      setTimeout(async () => {
        setSending(true);
        const tempUserMsg: DisplayMessage = {
          id: `temp-${Date.now()}`,
          session_id: session.id,
          role: "user",
          content: question,
          metadata: {},
          created_at: new Date().toISOString(),
        };
        setMessages([tempUserMsg]);
        setInput("");
        // Auto-title the session with the first message.
        const title = question.length > 80 ? question.slice(0, 80) + "..." : question;
        updateSession(session.id, title).catch(() => {});

        try {
          const response: ChatApiResponse = await sendChat(
            session.id,
            question,
          );
          setMessages([
            { ...tempUserMsg, id: `user-${response.message.id}` },
            {
              ...response.message,
              sources: response.sources,
              groundingStatus: response.grounding_status,
            },
          ]);
        } catch {
          setMessages([
            tempUserMsg,
            {
              id: `error-${Date.now()}`,
              session_id: session.id,
              role: "assistant",
              content:
                "Failed to get a response. Please check that the backend is running and the LLM provider is available.",
              metadata: {},
              created_at: new Date().toISOString(),
              groundingStatus: "error",
            },
          ]);
        } finally {
          setSending(false);
        }
      }, 50);
    } catch {
      // ignore
    }
  };

  return (
    <main className="h-screen bg-paper text-ink">
      <div className="grid h-screen grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_420px]">
        {/* Sidebar */}
        <div className="hidden lg:block">
          <SessionSidebar
            activeSessionId={activeSessionId}
            onSelectSession={setActiveSessionId}
            onNewChat={handleNewChat}
          />
        </div>

        {/* Chat area */}
        <section className="flex min-h-0 flex-col border-b border-line bg-paper lg:border-b-0 lg:border-r">
          {/* Chat header */}
          <header className="flex shrink-0 items-center justify-between border-b border-line px-6 py-4">
            <div>
              <h2 className="text-base font-semibold">
                {activeSessionId ? "Chat" : "Welcome"}
              </h2>
              <p className="text-xs text-neutral-500">
                {activeSessionId
                  ? "Ask product and growth questions grounded in Lenny's Podcast"
                  : "Create a new chat to get started"}
              </p>
            </div>
            {activeSessionId && (
              <button
                onClick={() => setShowArtifacts(!showArtifacts)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium ${
                  showArtifacts
                    ? "bg-accent text-white"
                    : "border border-line bg-white text-neutral-600 hover:bg-paper"
                }`}
              >
                <Sparkles size={14} />
                Artifacts
              </button>
            )}
          </header>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6">
            {!activeSessionId && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <div className="rounded-full bg-accent/10 p-4">
                  <Sparkles size={32} className="text-accent" />
                </div>
                <h3 className="mt-4 text-lg font-semibold">
                  Lenny Growth Assistant
                </h3>
                <p className="mt-2 max-w-md text-sm text-neutral-500">
                  Ask product management and growth questions grounded in
                  Lenny&apos;s Podcast transcript knowledge base.
                </p>
                <div className="mt-6 flex flex-wrap justify-center gap-2">
                  {[
                    "How should startups improve retention?",
                    "What have guests said about PMF?",
                    "Compare onboarding approaches",
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSuggestion(q)}
                      className="rounded-md border border-line bg-white px-3 py-2 text-xs text-neutral-600 hover:bg-paper"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {activeSessionId && messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <p className="text-sm text-neutral-400">
                  No messages yet. Ask a question to get started.
                </p>
              </div>
            )}

            <div className="space-y-5">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  sources={msg.sources}
                  groundingStatus={msg.groundingStatus}
                />
              ))}
              {sending && (
                <div className="flex gap-3">
                  <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
                    <Loader2 size={16} className="animate-spin" />
                  </div>
                  <div className="rounded-md border border-line bg-white p-4">
                    <p className="text-xs text-neutral-400">
                      Thinking...
                    </p>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input */}
          {activeSessionId && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="shrink-0 border-t border-line bg-white p-4"
            >
              <div className="flex items-end gap-3 rounded-md border border-line bg-paper p-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  className="min-h-12 flex-1 resize-none bg-transparent text-sm outline-none"
                  placeholder="Ask about onboarding, retention, PMF, pricing, or growth loops..."
                  rows={1}
                  disabled={sending}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || sending}
                  className="grid h-10 w-10 place-items-center rounded-md bg-accent text-white disabled:opacity-40"
                  aria-label="Send message"
                >
                  <Send size={18} />
                </button>
              </div>
            </form>
          )}
        </section>

        {/* Artifact panel */}
        {showArtifacts && (
          <div className="hidden lg:flex lg:flex-col">
            {activeArtifact ? (
              <ArtifactViewer
                artifact={activeArtifact}
                onClose={() => setActiveArtifact(null)}
              />
            ) : (
              <div className="flex h-full flex-col bg-white p-5">
                <h3 className="text-sm font-semibold">Generate Artifact</h3>
                <p className="mt-1 text-xs text-neutral-500">
                  Create a Markdown or HTML/CSS document from transcript
                  knowledge.
                </p>

                <div className="mt-4 flex gap-2">
                  <button
                    onClick={() => setArtifactType("markdown")}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                      artifactType === "markdown"
                        ? "bg-accent text-white"
                        : "border border-line text-neutral-600"
                    }`}
                  >
                    Markdown
                  </button>
                  <button
                    onClick={() => setArtifactType("html")}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium ${
                      artifactType === "html"
                        ? "bg-accent text-white"
                        : "border border-line text-neutral-600"
                    }`}
                  >
                    HTML/CSS
                  </button>
                </div>

                <textarea
                  value={artifactRequest}
                  onChange={(e) => setArtifactRequest(e.target.value)}
                  className="mt-3 min-h-[100px] resize-none rounded-md border border-line bg-paper p-3 text-sm outline-none"
                  placeholder="Describe what to generate... (e.g. 'Create a growth strategy memo' or 'Build a landing page explaining retention frameworks')"
                />

                <button
                  onClick={handleGenerateArtifact}
                  disabled={!artifactRequest.trim() || generatingArtifact}
                  className="mt-3 flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                >
                  {generatingArtifact ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Sparkles size={16} />
                  )}
                  Generate
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
