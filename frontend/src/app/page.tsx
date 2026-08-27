"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Loader2, Sparkles, FileText, Code2, PenLine } from "lucide-react";
import SessionSidebar from "@/components/SessionSidebar";
import ChatMessage from "@/components/ChatMessage";
import ArtifactViewer from "@/components/ArtifactViewer";
import {
  createSession,
  getSession,
  sendChat,
  updateSession,
  generateArtifact,
  listSessionArtifacts,
  getArtifact,
  generateShip30,
} from "@/lib/api";
import type {
  ArtifactStored,
  ArtifactListResponse,
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
  const [artifactHistory, setArtifactHistory] = useState<
    ArtifactListResponse["artifacts"]
  >([]);
  const [loadingArtifactId, setLoadingArtifactId] = useState<string | null>(
    null,
  );
  const [rightPanelTab, setRightPanelTab] = useState<"artifacts" | "ship30">(
    "artifacts",
  );
  const [ship30Topic, setShip30Topic] = useState("");
  const [generatingShip30, setGeneratingShip30] = useState(false);
  const [ship30Error, setShip30Error] = useState<string | null>(null);
  const [ship30Success, setShip30Success] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const refreshArtifactHistory = useCallback((sessionId: string) => {
    listSessionArtifacts(sessionId)
      .then((res) => setArtifactHistory(res.artifacts))
      .catch(() => setArtifactHistory([]));
  }, []);

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
      setArtifactHistory([]);
      setActiveArtifact(null);
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
    setActiveArtifact(null);
    refreshArtifactHistory(activeSessionId);
  }, [activeSessionId, refreshArtifactHistory]);

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
      const stored = await getArtifact(result.artifact_id);
      setActiveArtifact(stored);
      setShowArtifacts(true);
      setArtifactRequest("");
      refreshArtifactHistory(activeSessionId);
    } catch {
      // ignore
    } finally {
      setGeneratingArtifact(false);
    }
  };

  const handleOpenArtifact = async (artifactId: string) => {
    setLoadingArtifactId(artifactId);
    try {
      const stored = await getArtifact(artifactId);
      setActiveArtifact(stored);
    } catch {
      // ignore
    } finally {
      setLoadingArtifactId(null);
    }
  };

  const handleGenerateShip30 = async () => {
    if (!ship30Topic.trim() || !activeSessionId) return;
    setGeneratingShip30(true);
    setShip30Error(null);
    setShip30Success(null);
    try {
      const result = await generateShip30({
        topic: ship30Topic.trim(),
        sessionId: activeSessionId,
      });
      if (result.status !== "ok") {
        setShip30Error(
          result.error || "Not enough transcript evidence to write this essay.",
        );
        return;
      }
      // The essay is persisted as an assistant message server-side; reload
      // the session so it appears in the chat thread with its sources.
      const detail = await getSession(activeSessionId);
      const display: DisplayMessage[] = detail.messages.map((m) => ({
        ...m,
        sources: (m.metadata?.sources as Source[]) || [],
        groundingStatus: (m.metadata?.grounding_status as string) || undefined,
      }));
      setMessages(display);
      setShip30Success(`Essay added to chat (${result.word_count} words).`);
      setShip30Topic("");
    } catch {
      setShip30Error(
        "Failed to generate the essay. Check that the backend is running.",
      );
    } finally {
      setGeneratingShip30(false);
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
    setArtifactHistory([]);
    setShowArtifacts(false);
    setRightPanelTab("artifacts");
    setShip30Topic("");
    setShip30Error(null);
    setShip30Success(null);
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
        <div className="hidden h-screen min-h-0 overflow-hidden lg:block">
          <SessionSidebar
            activeSessionId={activeSessionId}
            onSelectSession={setActiveSessionId}
            onNewChat={handleNewChat}
          />
        </div>

        {/* Chat area */}
        <section className="flex h-screen min-h-0 flex-col overflow-hidden border-b border-line bg-paper lg:border-b-0 lg:border-r">
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
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
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
          <div className="hidden h-screen min-h-0 overflow-hidden lg:flex lg:flex-col">
            {activeArtifact ? (
              <ArtifactViewer
                artifact={activeArtifact}
                onClose={() => setActiveArtifact(null)}
              />
            ) : (
              <div className="flex h-full flex-col overflow-y-auto bg-white p-5">
                {/* Panel tabs */}
                <div className="mb-4 flex gap-1 rounded-md border border-line bg-paper p-1">
                  <button
                    onClick={() => setRightPanelTab("artifacts")}
                    className={`flex-1 rounded px-3 py-1.5 text-xs font-medium ${
                      rightPanelTab === "artifacts"
                        ? "bg-white text-ink shadow-sm"
                        : "text-neutral-500 hover:text-ink"
                    }`}
                  >
                    Artifacts
                  </button>
                  <button
                    onClick={() => setRightPanelTab("ship30")}
                    className={`flex-1 rounded px-3 py-1.5 text-xs font-medium ${
                      rightPanelTab === "ship30"
                        ? "bg-white text-ink shadow-sm"
                        : "text-neutral-500 hover:text-ink"
                    }`}
                  >
                    Ship 30 Essay
                  </button>
                </div>

                {rightPanelTab === "ship30" ? (
                  <>
                    <h3 className="text-sm font-semibold">
                      Ship 30 for 30 Essay
                    </h3>
                    <p className="mt-1 text-xs text-neutral-500">
                      Generate a ~1,250-word essay grounded in transcript
                      knowledge. It's added to this chat as a message.
                    </p>

                    <textarea
                      value={ship30Topic}
                      onChange={(e) => setShip30Topic(e.target.value)}
                      className="mt-3 min-h-[100px] resize-none rounded-md border border-line bg-paper p-3 text-sm outline-none"
                      placeholder="Describe the essay topic... (e.g. 'How to find product-market fit')"
                    />

                    {ship30Error && (
                      <p className="mt-2 text-xs text-red-600">
                        {ship30Error}
                      </p>
                    )}
                    {ship30Success && (
                      <p className="mt-2 text-xs text-green-700">
                        {ship30Success}
                      </p>
                    )}

                    <button
                      onClick={handleGenerateShip30}
                      disabled={!ship30Topic.trim() || generatingShip30}
                      className="mt-3 flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                    >
                      {generatingShip30 ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <PenLine size={16} />
                      )}
                      Generate Essay
                    </button>
                  </>
                ) : (
                  <>
                {artifactHistory.length > 0 && (
                  <div className="mb-5">
                    <h3 className="text-sm font-semibold">Artifact History</h3>
                    <p className="mt-1 text-xs text-neutral-500">
                      Previously generated artifacts in this chat.
                    </p>
                    <ul className="mt-3 space-y-2">
                      {artifactHistory.map((a) => (
                        <li key={a.id}>
                          <button
                            onClick={() => handleOpenArtifact(a.id)}
                            disabled={loadingArtifactId === a.id}
                            className="flex w-full items-center gap-2 rounded-md border border-line px-3 py-2 text-left text-xs hover:bg-paper disabled:opacity-50"
                          >
                            {a.type === "html" ? (
                              <Code2 size={14} className="shrink-0 text-accent" />
                            ) : (
                              <FileText size={14} className="shrink-0 text-accent" />
                            )}
                            <span className="flex-1 truncate font-medium text-ink">
                              {a.title}
                            </span>
                            {loadingArtifactId === a.id ? (
                              <Loader2 size={12} className="shrink-0 animate-spin" />
                            ) : (
                              <span className="shrink-0 text-neutral-400">
                                {new Date(a.created_at).toLocaleDateString()}
                              </span>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-4 border-t border-line pt-4" />
                  </div>
                )}

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
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
