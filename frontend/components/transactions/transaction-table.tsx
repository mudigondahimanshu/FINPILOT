"use client";

import * as React from "react";
import { type Transaction } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { ChevronLeft, ChevronRight, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  items: Transaction[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (p: number) => void;
  onEdit: (t: Transaction) => void;
  onDelete: (id: string) => void;
}

function amountClass(amount: string) {
  return Number(amount) >= 0 ? "text-success" : "text-destructive";
}

function formatAmount(amount: string, currency: string) {
  const n = Number(amount);
  if (currency === "INR") return formatINR(Math.abs(n));
  return `${currency} ${Math.abs(n).toFixed(2)}`;
}

export function TransactionTable({ items, total, page, pageSize, onPageChange, onEdit, onDelete }: Props) {
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
                  {t.category ? (
                    <span
                      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
                      style={{ backgroundColor: `${t.category.color}20`, color: t.category.color }}
                    >
                      {t.category.name}
                    </span>
                  ) : (
                    <span className="text-xs text-muted-foreground/60">—</span>
                  )}
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
