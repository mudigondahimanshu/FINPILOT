"use client";

import * as React from "react";
import { api, type TickerResult } from "@/lib/api";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";

interface Props {
  onSelect: (ticker: TickerResult) => void;
  placeholder?: string;
}

export function TickerSearch({ onSelect, placeholder = "Search symbol or company…" }: Props) {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<TickerResult[]>([]);
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!query.trim()) { setResults([]); setOpen(false); return; }
    const id = setTimeout(async () => {
      try {
        const r = await api.market.search(query, 8);
        setResults(r);
        setOpen(r.length > 0);
      } catch { setResults([]); }
    }, 200);
    return () => clearTimeout(id);
  }, [query]);

  // Close dropdown on outside click.
  React.useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  function pick(t: TickerResult) {
    onSelect(t);
    setQuery("");
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="pl-9 pr-8"
        />
        {query && (
          <button className="absolute right-2 top-1/2 -translate-y-1/2" onClick={() => { setQuery(""); setOpen(false); }}>
            <X className="h-4 w-4 text-muted-foreground hover:text-foreground" />
          </button>
        )}
      </div>
      {open && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-lg border border-border bg-card shadow-lg">
          {results.map((t) => (
            <button
              key={t.symbol}
              className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-secondary/60"
              onClick={() => pick(t)}
            >
              <div>
                <span className="font-mono font-semibold text-primary">{t.symbol.replace(/\.(NS|BO)$/, "")}</span>
                <span className="ml-2 text-muted-foreground">{t.name}</span>
              </div>
              <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {t.exchange}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
