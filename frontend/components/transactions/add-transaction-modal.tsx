"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api, type Transaction, type TransactionCreate } from "@/lib/api";
import { AlertCircle, Loader2, X } from "lucide-react";

interface Props {
  open: boolean;
  editing?: Transaction | null;
  onClose: () => void;
  onSaved: () => void;
}

export function AddTransactionModal({ open, editing, onClose, onSaved }: Props) {
  const [form, setForm] = React.useState<TransactionCreate>({
    date: new Date().toISOString().split("T")[0]!,
    amount: 0,
    description: "",
    source: "manual",
  });
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    if (editing) {
      setForm({
        date: editing.date.split("T")[0]!,
        amount: Number(editing.amount),
        description: editing.description,
        notes: editing.notes ?? undefined,
        category_id: editing.category_id ?? undefined,
        source: editing.source,
      });
    } else {
      setForm({ date: new Date().toISOString().split("T")[0]!, amount: 0, description: "", source: "manual" });
    }
    setError(null);
  }, [editing, open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      if (editing) {
        await api.transactions.update(editing.id, form);
      } else {
        await api.transactions.create({ ...form, date: new Date(form.date).toISOString() });
      }
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save transaction");
    } finally {
      setSaving(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl" style={{ animation: "rise 240ms ease-out both" }}>
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-semibold">{editing ? "Edit Transaction" : "Add Transaction"}</h2>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}><X className="h-4 w-4" /></Button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="txn-date">Date</Label>
            <Input id="txn-date" type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="txn-amount">Amount (₹)</Label>
            <p className="text-xs text-muted-foreground">Positive = income / credit, negative = expense</p>
            <Input
              id="txn-amount"
              type="number"
              step="0.01"
              placeholder="-1500.00"
              value={form.amount || ""}
              onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="txn-desc">Description</Label>
            <Input
              id="txn-desc"
              placeholder="Swiggy order, Salary credit…"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="txn-notes">Notes (optional)</Label>
            <Input
              id="txn-notes"
              placeholder="Any context…"
              value={form.notes ?? ""}
              onChange={(e) => setForm({ ...form, notes: e.target.value || undefined })}
            />
          </div>

          {error && (
            <p className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editing ? "Save changes" : "Add transaction"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
