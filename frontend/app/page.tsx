import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Button } from "@/components/ui/button";
import { ShieldCheck, LineChart, Bot, Activity } from "lucide-react";

const features = [
  {
    icon: LineChart,
    title: "Learns your money",
    body: "Auto-categorized spending, savings rate, and a 30-day forecast that updates as you go.",
  },
  {
    icon: Activity,
    title: "Paper-trade smarter",
    body: "Virtual ₹1,00,000, real market data, an order-matching engine — never a rupee of real money.",
  },
  {
    icon: Bot,
    title: "Explainable copilot",
    body: "Ask about your portfolio and get grounded answers with the sources it reasoned from.",
  },
  {
    icon: ShieldCheck,
    title: "Fraud guard",
    body: "Every login, trade, and transfer watched in real time with graph + anomaly detection.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            F
          </div>
          <span className="font-semibold tracking-tight">FinPilot</span>
        </div>
        <ThemeToggle />
      </header>

      <main className="container animate-fade-in py-16 sm:py-24">
        <section className="mx-auto max-w-3xl text-center">
          <p className="mb-4 inline-block rounded-md border border-border px-3 py-1 text-xs font-medium text-muted-foreground">
            AI-powered personal finance OS
          </p>
          <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-6xl">
            The copilot that learns your finances and{" "}
            <span className="text-primary">protects your money</span>.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-lg text-muted-foreground">
            Predict risk, forecast spending, and learn to trade — with
            bank-grade security and explainable AI that improves the more you
            use it.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Button size="lg" disabled>
              Get started
            </Button>
            <Button size="lg" variant="outline" disabled>
              View dashboard
            </Button>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Auth & dashboard land in Phase 1.2–1.5.
          </p>
        </section>

        <section className="mx-auto mt-20 grid max-w-5xl gap-4 sm:grid-cols-2">
          {features.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-lg border border-border bg-card p-6 transition-colors hover:border-primary/40"
            >
              <Icon className="h-5 w-5 text-primary" />
              <h3 className="mt-4 font-medium">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="container border-t border-border py-8">
        <p className="text-center text-xs text-muted-foreground">
          ⚠️ For educational purposes only. Not financial advice. Paper trading
          only — FinPilot never touches real money.
        </p>
      </footer>
    </div>
  );
}
