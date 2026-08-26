"use client";

import type { Source } from "@/types/api";

export default function SourceCard({
  source,
  index,
}: {
  source: Source;
  index: number;
}) {
  return (
    <div
      className="rounded-md border border-line bg-paper px-3 py-2 text-xs"
      title={source.source_path}
    >
      <span className="mr-1 font-semibold text-accent">[{index}]</span>
      {source.guest && (
        <span className="font-medium text-neutral-700">{source.guest}</span>
      )}
      {source.title && (
        <>
          {source.guest && <span className="text-neutral-400"> — </span>}
          <span className="text-neutral-600">{source.title}</span>
        </>
      )}
      {source.publish_date && (
        <span className="ml-1 text-neutral-400">({source.publish_date})</span>
      )}
    </div>
  );
}
