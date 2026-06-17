import Link from "next/link";
import { Lock, ShieldCheck, TrendingUp } from "lucide-react";

const trust = [
  { icon: Lock, label: "JWT + httpOnly refresh, bcrypt at rest" },
  { icon: ShieldCheck, label: "Real-time fraud & anomaly monitoring" },
  { icon: TrendingUp, label: "Paper money only — never a real rupee" },
];

/**
 * Two-pane auth layout: an atmospheric brand panel (hidden on small screens)
 * and a focused form column. Children render inside the form column.
 */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel */}
      <aside className="auth-aurora relative hidden overflow-hidden border-r border-border lg:flex">
        <div className="auth-grid auth-drift absolute inset-0" />
        <div className="relative z-10 flex w-full flex-col justify-between p-12">
          <Link href="/" className="flex w-fit items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
              F
            </div>
            <span className="font-semibold tracking-tight">FinPilot</span>
          </Link>

          <div
            className="max-w-md"
            style={{ animation: "rise 600ms ease-out both" }}
          >
            <p className="mb-5 font-mono text-xs uppercase tracking-[0.2em] text-primary">
              AI Personal Finance OS
            </p>
            <h1 className="text-balance text-4xl font-semibold leading-tight tracking-tight">
              The copilot that learns your finances and{" "}
              <span className="text-primary">protects your money</span>.
            </h1>
            <p className="mt-5 text-pretty text-muted-foreground">
              Forecast spending, paper-trade real markets, and ask an explainable
              copilot — behind bank-grade security.
            </p>
          </div>

          <ul className="space-y-3">
            {trust.map(({ icon: Icon, label }, i) => (
              <li
                key={label}
                className="flex items-center gap-3 text-sm text-muted-foreground"
                style={{
                  animation: `rise 600ms ease-out both`,
                  animationDelay: `${150 + i * 90}ms`,
                }}
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border bg-card/60">
                  <Icon className="h-3.5 w-3.5 text-primary" />
                </span>
                {label}
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Form column */}
      <main className="relative flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  );
}
