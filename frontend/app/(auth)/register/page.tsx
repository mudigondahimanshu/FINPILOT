"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleButton } from "@/components/auth/google-button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { useAuth } from "@/components/auth/auth-provider";
import { ApiError } from "@/lib/api";
import { AlertCircle, Check, Loader2 } from "lucide-react";

// Mirror the backend rules so users get instant feedback (min 8, letters+digits).
function passwordChecks(pw: string) {
  return [
    { label: "8+ characters", ok: pw.length >= 8 },
    { label: "A letter", ok: /[A-Za-z]/.test(pw) },
    { label: "A number", ok: /\d/.test(pw) },
  ];
}

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const checks = passwordChecks(password);
  const passwordValid = checks.every((c) => c.ok);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!passwordValid) {
      setError("Please meet all password requirements.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await register({
        email,
        password,
        full_name: fullName.trim() || undefined,
      });
      router.replace("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <AuthShell>
      <div style={{ animation: "rise 500ms ease-out both" }}>
        <div className="mb-8 flex items-center justify-between">
          <span className="hidden font-mono text-xs uppercase tracking-[0.2em] text-muted-foreground lg:block">
            Create account
          </span>
          <ThemeToggle />
        </div>

        <h2 className="text-2xl font-semibold tracking-tight">
          Create your account
        </h2>
        <p className="mt-1.5 text-sm text-muted-foreground">
          Start with virtual ₹1,00,000. No real money, ever.
        </p>

        <div className="mt-7">
          <GoogleButton label="Sign up with Google" />
        </div>

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            or
          </span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="fullName">Full name (optional)</Label>
            <Input
              id="fullName"
              type="text"
              autoComplete="name"
              placeholder="Ada Lovelace"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <ul className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
              {checks.map((c) => (
                <li
                  key={c.label}
                  className={`flex items-center gap-1 text-xs transition-colors ${
                    c.ok ? "text-success" : "text-muted-foreground/70"
                  }`}
                >
                  <Check
                    className={`h-3 w-3 ${c.ok ? "opacity-100" : "opacity-40"}`}
                  />
                  {c.label}
                </li>
              ))}
            </ul>
          </div>

          {error && (
            <p
              className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              role="alert"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </p>
          )}

          <Button
            type="submit"
            size="lg"
            className="w-full"
            disabled={submitting}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? "Creating account…" : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            Sign in
          </Link>
        </p>

        <p className="mt-6 text-center text-[11px] leading-relaxed text-muted-foreground/70">
          By continuing you agree this is an educational tool. Not financial
          advice. Paper trading only.
        </p>
      </div>
    </AuthShell>
  );
}
