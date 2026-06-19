"use client";

import * as React from "react";
import { Check, ChevronLeft, ChevronRight, Pencil, Sparkles, Trash2, X } from "lucide-react";
import {
  classifyTransaction,
  submitCategoryOverride,
  type Transaction,
} from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const ML_CATEGORIES = [
  "Food", "Transport", "Shopping", "Entertainment", "Health",
  "Utilities", "Travel", "Education", "Salary", "Investments",
  "Rent", "Insurance", "Dining", "Subscriptions", "Other",
];

interface Props {
  items: Transaction[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (p: number) => void;
  onEdit: (t: Transaction) => void;
  onDelete: (id: string) => void;
  onCategoryChanged?: () => void;
}

function amountClass(amount: string) {
  return Number(amount) >= 0 ? "text-success" : "text-destructive";
}

function formatAmount(amount: string, currency: string) {
  const n = Number(amount);
  if (currency === "INR") return formatINR(Math.abs(n));
  return `${currency} ${Math.abs(n).toFixed(2)}`;
}

function ConfidenceBadge({ confidence, override }: { confidence: number | null; override: boolean | null }) {
  if (!confidence) return null;
  const pct = Math.round(confidence * 100);
  const color =
    pct >= 80 ? "text-emerald-600 dark:text-emerald-400"
    : pct >= 60 ? "text-amber-600 dark:text-amber-400"
    : "text-muted-foreground";
  return (
    <span className={`ml-1 font-mono text-[9px] ${color}`} title={`ML confidence: ${pct}%`}>
      {override ? "✎" : <Sparkles className="inline h-2.5 w-2.5" />}{pct}%
    </span>
  );
}

function CategoryCell({
  transaction,
  onOverride,
}: {
  transaction: Transaction;
  onOverride: () => void;
}) {
  const [editing, setEditing] = React.useState(false);
  const [selected, setSelected] = React.useState(
    transaction.category?.name ?? ""
  );
  const [saving, setSaving] = React.useState(false);
  const [classifying, setClassifying] = React.useState(false);

  async function handleAutoClassify() {
    setClassifying(true);
    try {
      const result = await classifyTransaction(
        transaction.description,
        Number(transaction.amount),
        transaction.date.slice(0, 10),
      );
      setSelected(result.category);
      setEditing(true);
    } catch {
      // ignore
    } finally {
      setClassifying(false);
    }
  }

  async function handleSaveOverride() {
    if (!selected) return;
    setSaving(true);
    try {
      await submitCategoryOverride(
        transaction.id,
        selected,
        transaction.description,
        Number(transaction.amount),
        transaction.category?.name,
      );
      setEditing(false);
      onOverride();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded border border-border bg-background px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
          autoFocus
        >
          {ML_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <Button variant="ghost" size="icon" className="h-6 w-6 text-emerald-600" onClick={() => void handleSaveOverride()} disabled={saving}>
          <Check className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setEditing(false)}>
          <X className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 group">
      {transaction.category ? (
        <span
          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: `${transaction.category.color}20`, color: transaction.category.color }}
        >
          {transaction.category.name}
          <ConfidenceBadge confidence={transaction.ml_confidence} override={transaction.ml_category_override} />
        </span>
      ) : (
        <span className="text-xs text-muted-foreground/60">—</span>
      )}
      <div className="hidden group-hover:flex items-center gap-0.5">
        {!transaction.category && (
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5"
            title="Auto-classify with AI"
            onClick={() => void handleAutoClassify()}
            disabled={classifying}
          >
            <Sparkles className="h-3 w-3 text-primary" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-5 w-5"
          title="Override category"
          onClick={() => setEditing(true)}
        >
          <Pencil className="h-3 w-3 text-muted-foreground" />
        </Button>
      </div>
    </div>
  );
}

export function TransactionTable({
  items,
  total,
  page,
  pageSize,
  onPageChange,
  onEdit,
  onDelete,
  onCategoryChanged,
}: Props) {
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-card/60">
            <tr>
              {["Date", "Description", "Category", "Amount", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-sm text-muted-foreground">
                  No transactions found.
                </td>
              </tr>
            )}
            {items.map((t) => (
              <tr key={t.id} className="transition-colors hover:bg-secondary/40">
                <td className="px-4 py-3 tabular text-muted-foreground whitespace-nowrap">
                  {new Date(t.date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                </td>
                <td className="px-4 py-3 max-w-xs">
                  <p className="truncate font-medium">{t.description}</p>
                  {t.merchant && <p className="truncate text-xs text-muted-foreground">{t.merchant}</p>}
                </td>
                <td className="px-4 py-3">
                  <CategoryCell transaction={t} onOverride={onCategoryChanged ?? (() => {})} />
                </td>
                <td className={`px-4 py-3 tabular font-semibold whitespace-nowrap ${amountClass(t.amount)}`}>
                  {Number(t.amount) >= 0 ? "+" : "−"}{formatAmount(t.amount, t.currency)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit(t)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive/70 hover:text-destructive" onClick={() => onDelete(t.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-border px-4 py-3">
          <p className="text-xs text-muted-foreground">
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
          </p>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="h-8 w-8" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="tabular text-xs text-muted-foreground">{page} / {totalPages}</span>
            <Button variant="ghost" size="icon" className="h-8 w-8" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
