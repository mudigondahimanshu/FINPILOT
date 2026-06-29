"use client";

import * as React from "react";
import { type SentimentResult } from "@/lib/api";

interface Props {
  data: SentimentResult;
}

function ScoreBadge({ label, score }: { label: string; score: number }) {
  const color =
    label === "Bullish"
      ? "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800"
      : label === "Bearish"
        ? "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800"
        : "text-muted-foreground bg-secondary border-border";

  const bar = Math.abs(score) * 100;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium ${color}`}>
      <span
        className="inline-block h-1.5 rounded-full bg-current"
        style={{ width: `${Math.max(4, bar * 0.4)}px` }}
      />
      {label} {score > 0 ? "+" : ""}{score.toFixed(2)}
    </span>
  );
}

export function SentimentFeed({ data }: Props) {
  const [expanded, setExpanded] = React.useState(false);
  const articles = data.articles ?? [];
  const shown = expanded ? articles : articles.slice(0, 4);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            {data.symbol}
          </span>
          <ScoreBadge label={data.overall_label} score={data.overall_score} />
          {data.cached && (
            <span className="font-mono text-[10px] text-muted-foreground/60">cached</span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">{articles.length} articles</span>
      </div>

      <ul className="space-y-2">
        {shown.map((article, i) => (
          <li
            key={i}
            className="flex items-start justify-between gap-3 rounded-md border border-border/60 bg-card/40 p-2.5"
          >
            <div className="min-w-0 flex-1">
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="line-clamp-2 text-sm font-medium leading-snug hover:underline"
              >
                {article.title}
              </a>
              <div className="mt-1 flex items-center gap-2">
                <span className="font-mono text-[10px] text-muted-foreground">{article.source}</span>
                <span className="text-[10px] text-muted-foreground">
                  {new Date(article.published).toLocaleDateString()}
                </span>
              </div>
            </div>
            <ScoreBadge label={article.label} score={article.score} />
          </li>
        ))}
      </ul>

      {articles.length > 4 && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          {expanded ? "Show less" : `Show ${articles.length - 4} more`}
        </button>
      )}
    </div>
  );
}
