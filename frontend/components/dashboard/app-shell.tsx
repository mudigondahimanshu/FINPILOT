"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  LayoutDashboard,
  LineChart,
  LogOut,
  ShieldCheck,
  Wallet,
} from "lucide-react";
import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const nav = [
  { icon: LayoutDashboard, label: "Overview", href: "/dashboard" },
  { icon: Wallet, label: "Spending", href: "/transactions" },
  { icon: LineChart, label: "Paper trading", href: null },
  { icon: Bot, label: "Copilot", href: null },
  { icon: ShieldCheck, label: "Fraud guard", href: null },
];

function initials(name: string | null, email: string): string {
  if (name?.trim()) {
    return name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((p) => p[0]!.toUpperCase())
      .join("");
  }
  return email[0]!.toUpperCase();
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();

  return (
    <div className="grid min-h-screen lg:grid-cols-[15rem_1fr]">
      {/* Sidebar */}
      <aside className="hidden flex-col border-r border-border bg-card/40 p-4 lg:flex">
        <Link href="/dashboard" className="mb-8 flex items-center gap-2.5 px-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            F
          </span>
          <span className="font-semibold tracking-tight">FinPilot</span>
        </Link>

        <nav className="flex flex-1 flex-col gap-1">
          {nav.map(({ icon: Icon, label, href }) => {
            const isActive = href ? pathname.startsWith(href) : false;
            const cls = `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
              isActive
                ? "bg-secondary font-medium text-foreground"
                : "text-muted-foreground hover:bg-secondary/60"
            } ${!href ? "opacity-50 pointer-events-none" : ""}`;
            return href ? (
              <Link key={label} href={href} className={cls}>
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            ) : (
              <span key={label} className={cls}>
                <Icon className="h-4 w-4" />
                {label}
                <span className="ml-auto font-mono text-[9px] uppercase tracking-wide text-muted-foreground/60">
                  soon
                </span>
              </span>
            );
          })}
        </nav>

        <div className="mt-4 rounded-md border border-border p-3">
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Educational tool. Not financial advice. Paper trading only.
          </p>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex flex-col">
        <header className="flex h-16 items-center justify-between border-b border-border px-6">
          <div className="flex items-center gap-2 lg:hidden">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
              F
            </span>
            <span className="font-semibold tracking-tight">FinPilot</span>
          </div>
          <div className="hidden font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground lg:block">
            Dashboard
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-secondary text-xs font-semibold">
                {user ? initials(user.full_name, user.email) : "·"}
              </span>
              <div className="hidden sm:block">
                <p className="text-sm font-medium leading-none">
                  {user?.full_name ?? user?.email}
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {user?.email}
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
