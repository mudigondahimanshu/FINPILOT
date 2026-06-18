"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { api, type CsvUploadResult } from "@/lib/api";
import { CheckCircle, FileUp, Loader2, XCircle } from "lucide-react";

interface Props {
  onImported: () => void;
}

export function CsvUpload({ onImported }: Props) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [result, setResult] = React.useState<CsvUploadResult | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setResult(null);
    setError(null);
    try {
      const res = await api.transactions.uploadCsv(file);
      setResult(res);
      if (res.imported > 0) onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  return (
    <div className="space-y-3">
      <div
        className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border px-6 py-8 transition-colors hover:border-primary/50 hover:bg-secondary/30"
        onClick={() => inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={(e) => e.preventDefault()}
      >
        {uploading ? (
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        ) : (
          <FileUp className="h-8 w-8 text-muted-foreground" />
        )}
        <div className="text-center">
          <p className="text-sm font-medium">Drop a CSV file here, or click to browse</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Required columns: <span className="font-mono">date, amount, description</span>
            <br />Optional: <span className="font-mono">category, notes, merchant, currency</span>
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
      </div>

      {error && (
        <p className="flex items-center gap-2 text-sm text-destructive"><XCircle className="h-4 w-4" />{error}</p>
      )}

      {result && (
        <div className="rounded-lg border border-border bg-card/60 p-4 text-sm space-y-1">
          <p className="flex items-center gap-2 font-medium text-success">
            <CheckCircle className="h-4 w-4" />
            Imported {result.imported} transaction{result.imported !== 1 ? "s" : ""}
            {result.skipped > 0 && <span className="text-muted-foreground">(skipped {result.skipped})</span>}
          </p>
          {result.errors.map((e, i) => (
            <p key={i} className="ml-6 text-xs text-muted-foreground">{e}</p>
          ))}
        </div>
      )}
    </div>
  );
}
