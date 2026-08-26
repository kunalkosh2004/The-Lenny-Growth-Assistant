"use client";

import { X, FileText, Code } from "lucide-react";
import type { ArtifactStored } from "@/types/api";

function renderMarkdown(content: string): string {
  // Simple markdown → HTML conversion for display.
  // In production, use a proper library like react-markdown.
  let html = content
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold mt-4 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-semibold mt-6 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold mt-8 mb-3">$1</h1>')
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Unordered list items
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    // Ordered list items
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
    // Blockquotes
    .replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-accent pl-4 italic text-neutral-600">$1</blockquote>')
    // Horizontal rules
    .replace(/^---$/gm, '<hr class="my-4 border-line" />')
    // Line breaks
    .replace(/\n\n/g, '</p><p class="mb-3 leading-6">')
    .replace(/\n/g, '<br/>');

  html = '<p class="mb-3 leading-6">' + html + '</p>';
  return html;
}

function MarkdownViewer({ content }: { content: string }) {
  return (
    <div
      className="prose prose-sm max-w-none text-sm"
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}

function HTMLViewer({ content }: { content: string }) {
  // Render HTML in a sandboxed iframe. The sandbox attribute prevents:
  // - allow-scripts: JavaScript execution blocked
  // - allow-forms: Form submission blocked
  // - allow-popups: Popups blocked
  // Only allow-same-origin is needed for CSS to work.
  return (
    <div className="rounded-md border border-line bg-white">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2">
        <Code size={14} className="text-accent" />
        <span className="text-xs font-medium text-neutral-600">
          HTML/CSS Preview (sandboxed)
        </span>
      </div>
      <iframe
        srcDoc={content}
        sandbox="allow-same-origin"
        className="h-[500px] w-full"
        title="Artifact preview"
      />
    </div>
  );
}

export default function ArtifactViewer({
  artifact,
  onClose,
}: {
  artifact: ArtifactStored;
  onClose: () => void;
}) {
  return (
    <aside className="flex h-full flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line px-5 py-4">
        <div className="flex items-center gap-2">
          <FileText size={18} className="text-accent" />
          <div>
            <h2 className="text-sm font-semibold">{artifact.title}</h2>
            <p className="text-xs text-neutral-500 capitalize">
              {artifact.type} artifact
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="grid h-8 w-8 place-items-center rounded-md hover:bg-paper"
          aria-label="Close artifact viewer"
        >
          <X size={16} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5">
        {artifact.type === "html" ? (
          <HTMLViewer content={artifact.content} />
        ) : (
          <MarkdownViewer content={artifact.content} />
        )}
      </div>
    </aside>
  );
}
