import { FileText, MessageSquarePlus, Send, ShieldCheck } from "lucide-react";

const sources = [
  "Finding product-market fit",
  "Retention and activation",
  "Growth loops and positioning",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)_420px]">
        <aside className="border-b border-line bg-white px-5 py-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-accent">
                Internal AI
              </p>
              <h1 className="mt-1 text-2xl font-semibold">Lenny Growth Assistant</h1>
            </div>
            <button
              className="grid h-10 w-10 place-items-center rounded-md border border-line bg-paper"
              aria-label="Start new chat"
            >
              <MessageSquarePlus size={19} />
            </button>
          </div>

          <div className="mt-8 rounded-md border border-line bg-paper p-4">
            <p className="text-sm font-semibold">Model Provider</p>
            <p className="mt-2 text-sm text-neutral-700">Ollama Local</p>
            <p className="mt-1 text-xs text-warn">Status checks start in Milestone 4</p>
          </div>

          <nav className="mt-8 space-y-2" aria-label="Chat sessions">
            {["New research thread", "Activation ideas", "Artifact drafts"].map((item) => (
              <button
                key={item}
                className="block w-full rounded-md px-3 py-2 text-left text-sm hover:bg-paper"
              >
                {item}
              </button>
            ))}
          </nav>
        </aside>

        <section className="flex min-h-[680px] flex-col border-b border-line bg-paper lg:border-b-0 lg:border-r">
          <header className="border-b border-line px-6 py-5">
            <p className="text-sm text-neutral-600">Grounded chat foundation</p>
            <h2 className="mt-1 text-xl font-semibold">Ask product and growth questions</h2>
          </header>

          <div className="flex-1 space-y-5 px-6 py-6">
            <div className="max-w-[760px] rounded-md border border-line bg-white p-4">
              <p className="text-sm font-semibold">Assistant</p>
              <p className="mt-2 text-sm leading-6 text-neutral-700">
                Milestone 1 establishes the application shell. Grounded retrieval,
                citations, sessions, and artifact generation will arrive in the
                next milestones.
              </p>
            </div>

            <div className="ml-auto max-w-[680px] rounded-md bg-accent p-4 text-white">
              <p className="text-sm font-semibold">You</p>
              <p className="mt-2 text-sm leading-6">
                How should an early-stage startup improve retention?
              </p>
            </div>

            <div className="max-w-[760px] rounded-md border border-line bg-white p-4">
              <p className="text-sm font-semibold">Planned source display</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {sources.map((source) => (
                  <span
                    key={source}
                    className="rounded-md border border-line bg-paper px-3 py-1 text-xs"
                  >
                    {source}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <form className="border-t border-line bg-white p-4">
            <div className="flex items-end gap-3 rounded-md border border-line bg-paper p-3">
              <textarea
                aria-label="Message"
                className="min-h-12 flex-1 resize-none bg-transparent text-sm outline-none"
                placeholder="Ask about onboarding, retention, PMF, pricing, or growth loops..."
              />
              <button
                className="grid h-10 w-10 place-items-center rounded-md bg-accent text-white"
                aria-label="Send message"
                type="submit"
              >
                <Send size={18} />
              </button>
            </div>
          </form>
        </section>

        <aside className="bg-white px-6 py-5">
          <div className="flex items-center gap-2">
            <FileText size={20} />
            <h2 className="text-lg font-semibold">Artifact Viewer</h2>
          </div>
          <div className="mt-5 rounded-md border border-line bg-paper p-5">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <ShieldCheck size={18} className="text-accent" />
              Sandboxed preview planned
            </div>
            <p className="mt-3 text-sm leading-6 text-neutral-700">
              Markdown and HTML/CSS artifacts will render here beside the chat.
              Generated HTML will be treated as untrusted content and isolated
              in a restrictive iframe.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
