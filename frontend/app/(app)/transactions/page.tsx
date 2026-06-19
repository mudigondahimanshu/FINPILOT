"use client";

import * as React from "react";
import { api, type Transaction, type TransactionFilters, type SpendingSummary } from "@/lib/api";
import { TransactionFiltersBar } from "@/components/transactions/transaction-filters";
import { TransactionTable } from "@/components/transactions/transaction-table";
import { AddTransactionModal } from "@/components/transactions/add-transaction-modal";
import { CsvUpload } from "@/components/transactions/csv-upload";
import { SpendingCharts } from "@/components/transactions/spending-charts";
import { Button } from "@/components/ui/button";
import { formatINR } from "@/lib/utils";
import { Download, Loader2, Plus, TrendingDown, TrendingUp, Wallet } from "lucide-react";

export default function TransactionsPage() {
  const [filters, setFilters] = React.useState<TransactionFilters>({ page: 1, page_size: 50 });
  const [items, setItems] = React.useState<Transaction[]>([]);
  const [total, setTotal] = React.useState(0);
  const [summary, setSummary] = React.useState<SpendingSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [showAdd, setShowAdd] = React.useState(false);
  const [showCsv, setShowCsv] = React.useState(false);
  const [editing, setEditing] = React.useState<Transaction | null>(null);

  const fetchAll = React.useCallback(async () => {
    setLoading(true);
    try {
      const [page, sum] = await Promise.all([
        api.transactions.list(filters),
        api.transactions.summary(),
      ]);
      setItems(page.items);
      setTotal(page.total);
      setSummary(sum);
    } catch {
      // Silently ignore — backend may not be reachable during static preview.
    } finally {
      setLoading(false);
    }
  }, [filters]);

  React.useEffect(() => { fetchAll(); }, [fetchAll]);

  async function handleDelete(id: string) {
    if (!confirm("Delete this transaction?")) return;
    await api.transactions.delete(id);
    fetchAll();
  }

  const income = summary ? Number(summary.total_income) : 0;
  const expenses = summary ? Number(summary.total_expenses) : 0;
  const savings = income - expenses;

  return (
    <div className="mx-auto max-w-6xl space-y-8" style={{ animation: "rise 450ms ease-out both" }}>
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Transactions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} record{total !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowCsv((v) => !v)}>
            <Download className="h-4 w-4" />
            Import CSV
          </Button>
          <Button size="sm" onClick={() => { setEditing(null); setShowAdd(true); }}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: TrendingUp, label: "Income", value: income, color: "text-success" },
          { icon: TrendingDown, label: "Expenses", value: expenses, color: "text-destructive" },
          { icon: Wallet, label: "Net savings", value: savings, color: savings >= 0 ? "text-success" : "text-destructive" },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="rounded-lg border border-border bg-card p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</span>
              <Icon className={`h-4 w-4 ${color}`} />
            </div>
            <p className={`mt-3 text-2xl font-semibold tabular ${color}`}>
              {summary ? formatINR(Math.abs(value)) : "—"}
            </p>
          </div>
        ))}
      </div>

      {/* CSV upload panel */}
      {showCsv && (
        <div className="rounded-lg border border-border bg-card p-5">
          <h3 className="mb-4 text-sm font-medium">Import from CSV</h3>
          <CsvUpload onImported={fetchAll} />
        </div>
      )}

      {/* Charts */}
      {summary && <SpendingCharts summary={summary} />}

      {/* Filters + table */}
      <div className="space-y-4">
        <TransactionFiltersBar filters={filters} onChange={setFilters} />
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : (
          <TransactionTable
            items={items}
            total={total}
            page={filters.page ?? 1}
            pageSize={filters.page_size ?? 50}
            onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
            onEdit={(t) => { setEditing(t); setShowAdd(true); }}
            onDelete={handleDelete}
            onCategoryChanged={fetchAll}
          />
        )}
      </div>

      <AddTransactionModal
        open={showAdd}
        editing={editing}
        onClose={() => { setShowAdd(false); setEditing(null); }}
        onSaved={fetchAll}
      />
    </div>
  );
}
