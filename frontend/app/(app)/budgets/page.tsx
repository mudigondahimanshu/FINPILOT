"use client";

import * as React from "react";
import { api, type Budget, type BudgetStatus, type Category } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2, Plus, Trash2, X } from "lucide-react";

function BudgetCard({
  status,
  onDelete,
  onAmount,
}: {
  status: BudgetStatus;
  onDelete: () => void;
  onAmount: (amount: number) => void;
}) {
  const pct = Math.min(100, Number(status.utilisation) * 100);
  const color = status.over_budget ? "#EF4444" : pct > 80 ? "#F59E0B" : "#22C55E";
  const [editing, setEditing] = React.useState(false);
  const [amount, setAmount] = React.useState(String(Number(status.budget_amount)));

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold">{status.category_name}</h3>
          <p className="mt-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
            {status.period}
          </p>
        </div>
        <button
          onClick={onDelete}
          aria-label={`Delete ${status.category_name} budget`}
          className="text-muted-foreground transition-colors hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      <div className="mt-4">
        <div className="flex items-baseline justify-between">
          <span className="tabular text-xl font-semibold" style={{ color }}>
            {formatINR(Number(status.spent))}
          </span>
          {editing ? (
            <form
              className="flex items-center gap-1"
              onSubmit={(e) => {
                e.preventDefault();
                const v = Number(amount);
                if (v > 0) onAmount(v);
                setEditing(false);
              }}
            >
              <Input
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                type="number"
                min="1"
                className="h-7 w-24 text-xs"
                autoFocus
              />
              <Button type="submit" size="sm" className="h-7 px-2 text-xs">
                Save
              </Button>
            </form>
          ) : (
            <button
              className="tabular text-xs text-muted-foreground hover:text-foreground hover:underline"
              onClick={() => setEditing(true)}
            >
              of {formatINR(Number(status.budget_amount))}
            </button>
          )}
        </div>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${pct}%`, backgroundColor: color }}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {status.over_budget
            ? `Over by ${formatINR(Math.abs(Number(status.remaining)))}`
            : `${formatINR(Number(status.remaining))} left this month`}
        </p>
      </div>
    </div>
  );
}

export default function BudgetsPage() {
  const [statuses, setStatuses] = React.useState<BudgetStatus[]>([]);
  const [budgets, setBudgets] = React.useState<Budget[]>([]);
  const [categories, setCategories] = React.useState<Category[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [showForm, setShowForm] = React.useState(false);
  const [categoryId, setCategoryId] = React.useState("");
  const [amount, setAmount] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      const [st, bg, cats] = await Promise.all([
        api.budgets.status(),
        api.budgets.list(),
        api.budgets.categories(),
      ]);
      setStatuses(st);
      setBudgets(bg);
      setCategories(cats);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load budgets");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  const budgeted = new Set(budgets.map((b) => b.category_id));
  const available = categories.filter((c) => !budgeted.has(c.id));

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!categoryId || Number(amount) <= 0) return;
    setSaving(true);
    try {
      await api.budgets.create({ category_id: categoryId, amount: Number(amount) });
      setShowForm(false);
      setCategoryId("");
      setAmount("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the budget");
    } finally {
      setSaving(false);
    }
  }

  const totalBudget = statuses.reduce((s, b) => s + Number(b.budget_amount), 0);
  const totalSpent = statuses.reduce((s, b) => s + Number(b.spent), 0);

  return (
    <div className="mx-auto max-w-5xl space-y-6" style={{ animation: "rise 450ms ease-out both" }}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Budgets</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Set a monthly limit per category — spending is tracked automatically.
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showForm ? "Cancel" : "New budget"}
        </Button>
      </div>

      {statuses.length > 0 && (
        <div className="flex items-baseline gap-2 rounded-lg border border-border bg-card px-5 py-3 text-sm">
          <span className="text-muted-foreground">This month:</span>
          <span className="tabular font-semibold">{formatINR(totalSpent)}</span>
          <span className="text-muted-foreground">
            spent of <span className="tabular">{formatINR(totalBudget)}</span> budgeted
          </span>
        </div>
      )}

      {showForm && (
        <form
          onSubmit={create}
          className="grid gap-4 rounded-lg border border-border bg-card p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
        >
          <div className="space-y-1.5">
            <Label htmlFor="budget-category">Category</Label>
            <select
              id="budget-category"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              required
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value="">Choose a category…</option>
              {available.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="budget-amount">Monthly limit (₹)</Label>
            <Input
              id="budget-amount"
              type="number"
              min="1"
              placeholder="10000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </div>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Create budget
          </Button>
        </form>
      )}

      {error && (
        <p
          className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          <AlertCircle className="h-4 w-4" /> {error}
        </p>
      )}

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
        </div>
      ) : statuses.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border py-16 text-center">
          <p className="text-sm text-muted-foreground">
            No budgets yet. Create one to get alerts before a category runs hot.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {statuses.map((s) => (
            <BudgetCard
              key={s.budget_id}
              status={s}
              onDelete={() => {
                void api.budgets.delete(s.budget_id).then(load);
              }}
              onAmount={(v) => {
                void api.budgets.update(s.budget_id, { amount: v }).then(load);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
