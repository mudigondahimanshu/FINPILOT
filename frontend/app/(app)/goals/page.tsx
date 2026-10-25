"use client";

import * as React from "react";
import { api, type Goal, type GoalSavingsSummary } from "@/lib/api";
import { formatINR } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, Loader2, PartyPopper, Plus, Trash2, X } from "lucide-react";

/** Radial progress ring with the percentage in the middle. */
function ProgressRing({ pct }: { pct: number }) {
  const r = 34;
  const circ = 2 * Math.PI * r;
  const filled = circ * (Math.min(pct, 100) / 100);
  const done = pct >= 100;
  return (
    <svg viewBox="0 0 80 80" className="h-20 w-20" aria-label={`${pct.toFixed(0)}% saved`}>
      <circle cx="40" cy="40" r={r} fill="none" stroke="hsl(0 0% 16%)" strokeWidth="7" />
      <circle
        cx="40"
        cy="40"
        r={r}
        fill="none"
        stroke={done ? "#22C55E" : "#6366F1"}
        strokeWidth="7"
        strokeDasharray={`${filled} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 40 40)"
        style={{ transition: "stroke-dasharray 800ms ease-out" }}
      />
      <text
        x="40"
        y="45"
        textAnchor="middle"
        fontSize="16"
        fontWeight="600"
        fill={done ? "#22C55E" : "currentColor"}
      >
        {pct.toFixed(0)}%
      </text>
    </svg>
  );
}

function GoalCard({
  goal,
  availableSavings,
  onContribute,
  onDelete,
}: {
  goal: Goal;
  availableSavings: number;
  onContribute: (amount: number) => Promise<void>;
  onDelete: () => void;
}) {
  const [amount, setAmount] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [contributeError, setContributeError] = React.useState<string | null>(null);
  const done = goal.progress_pct >= 100;

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <ProgressRing pct={goal.progress_pct} />
          <div>
            <h3 className="text-sm font-semibold">{goal.name}</h3>
            <p className="tabular mt-1 text-xs text-muted-foreground">
              {formatINR(Number(goal.saved_amount))} of {formatINR(Number(goal.target_amount))}
            </p>
            {done ? (
              <p className="mt-1.5 flex items-center gap-1 text-xs font-medium text-success">
                <PartyPopper className="h-3.5 w-3.5" /> Goal reached
              </p>
            ) : goal.projected_completion ? (
              <p className="mt-1.5 text-xs text-muted-foreground">
                At your savings pace:{" "}
                <span className="font-medium text-foreground">
                  {new Date(goal.projected_completion).toLocaleDateString("en-IN", {
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              </p>
            ) : (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Add income history to see a projection.
              </p>
            )}
            {goal.monthly_needed && !done && (
              <p className="text-xs text-muted-foreground">
                Needs <span className="tabular">{formatINR(Number(goal.monthly_needed))}</span>/mo
                to hit{" "}
                {goal.target_date &&
                  new Date(goal.target_date).toLocaleDateString("en-IN", {
                    month: "short",
                    year: "numeric",
                  })}
              </p>
            )}
          </div>
        </div>
        <button
          onClick={onDelete}
          aria-label={`Delete goal ${goal.name}`}
          className="text-muted-foreground transition-colors hover:text-destructive"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {!done && (
        <form
          className="mt-4 flex items-center gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            const v = Number(amount);
            if (v <= 0) return;
            setBusy(true);
            setContributeError(null);
            try {
              await onContribute(v);
              setAmount("");
            } catch (err) {
              setContributeError(err instanceof Error ? err.message : "Couldn't add savings");
            } finally {
              setBusy(false);
            }
          }}
        >
          <Input
            type="number"
            min="1"
            max={availableSavings}
            placeholder="Add amount (₹)"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="h-9"
          />
          <Button
            type="submit"
            size="sm"
            disabled={busy || Number(amount) <= 0 || Number(amount) > availableSavings}
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add savings"}
          </Button>
        </form>
      )}
      {!done && (
        <p className="mt-2 text-xs text-muted-foreground">
          Available to allocate: {formatINR(availableSavings)}
        </p>
      )}
      {contributeError && (
        <p className="mt-2 text-xs text-destructive" role="alert">
          {contributeError}
        </p>
      )}
    </div>
  );
}

export default function GoalsPage() {
  const [goals, setGoals] = React.useState<Goal[]>([]);
  const [savings, setSavings] = React.useState<GoalSavingsSummary | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [showForm, setShowForm] = React.useState(false);
  const [name, setName] = React.useState("");
  const [target, setTarget] = React.useState("");
  const [targetDate, setTargetDate] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      const [nextGoals, nextSavings] = await Promise.all([
        api.goals.list(),
        api.goals.savingsSummary(),
      ]);
      setGoals(nextGoals);
      setSavings(nextSavings);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load goals");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || Number(target) <= 0) return;
    setSaving(true);
    try {
      await api.goals.create({
        name: name.trim(),
        target_amount: Number(target),
        target_date: targetDate || null,
      });
      setShowForm(false);
      setName("");
      setTarget("");
      setTargetDate("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the goal");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6" style={{ animation: "rise 450ms ease-out both" }}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Savings goals</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Name what you&rsquo;re saving for — FinPilot projects when you&rsquo;ll get there.
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showForm ? "Cancel" : "New goal"}
        </Button>
      </div>

      {savings && (
        <section
          className="rounded-lg border border-border bg-card p-5"
          aria-labelledby="savings-overview-title"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 id="savings-overview-title" className="text-base font-semibold">
                Savings overview
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Income minus spending gives net savings. Adding money to a goal moves it out of the
                available balance.
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground">Available to allocate</p>
              <p className="tabular text-2xl font-semibold text-success">
                {formatINR(Number(savings.available_savings))}
              </p>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <SavingsMetric label="Income" value={Number(savings.total_income)} />
            <SavingsMetric label="Spending" value={Number(savings.total_expenses)} />
            <SavingsMetric
              label="Already assigned to goals"
              value={Number(savings.allocated_to_goals)}
            />
          </div>
          {Number(savings.net_savings) < 0 && (
            <p className="mt-3 text-xs text-warning" role="status">
              Spending is higher than recorded income by{" "}
              {formatINR(Math.abs(Number(savings.net_savings)))}. Goal contributions cannot exceed
              available funds.
            </p>
          )}
        </section>
      )}

      {showForm && (
        <form
          onSubmit={create}
          className="grid gap-4 rounded-lg border border-border bg-card p-5 sm:grid-cols-[1.5fr_1fr_1fr_auto] sm:items-end"
        >
          <div className="space-y-1.5">
            <Label htmlFor="goal-name">Goal</Label>
            <Input
              id="goal-name"
              placeholder="Emergency fund, Goa trip, new laptop…"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="goal-target">Target (₹)</Label>
            <Input
              id="goal-target"
              type="number"
              min="1"
              placeholder="100000"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="goal-date">Target date (optional)</Label>
            <Input
              id="goal-date"
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            Create goal
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
      ) : goals.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border py-16 text-center">
          <p className="text-sm text-muted-foreground">
            Nothing here yet. A goal with a number beats a wish — create your first one.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {goals.map((g) => (
            <GoalCard
              key={g.id}
              goal={g}
              availableSavings={Number(savings?.available_savings ?? 0)}
              onContribute={async (v) => {
                await api.goals.contribute(g.id, v);
                await load();
              }}
              onDelete={() => {
                void api.goals.delete(g.id).then(load);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SavingsMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border/70 bg-background/50 px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="tabular mt-1 text-sm font-medium">{formatINR(value)}</p>
    </div>
  );
}
