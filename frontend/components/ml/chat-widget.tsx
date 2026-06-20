"use client";

import * as React from "react";
import { Bot, Loader2, Send, Sparkles, ThumbsDown, ThumbsUp, User } from "lucide-react";
import { copilotChat, submitCopilotFeedback } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface Message {
  role: "user" | "assistant";
  content: string;
  question?: string;
  reasoning?: string;
  sources?: { id: string; content: string; similarity: number }[];
  feedback?: "up" | "down" | null;
  personalized?: boolean;
}

const STARTERS = [
  "How should I rebalance my portfolio?",
  "What are signs of fraudulent transactions?",
  "Explain SIP vs lump sum investing",
  "How do I calculate my tax liability on capital gains?",
];

export function ChatWidget() {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [input, setInput] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const bottomRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);

  async function handleFeedback(idx: number, thumbsUp: boolean) {
    const msg = messages[idx];
    if (!msg || msg.role !== "assistant" || msg.feedback) return;
    setMessages((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, feedback: thumbsUp ? "up" : "down" } : m)),
    );
    try {
      await submitCopilotFeedback(msg.question ?? "", msg.content, thumbsUp);
    } catch {
      // ignore — feedback is best-effort
    }
  }

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    const question = text.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const res = await copilotChat(question, history);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          question,
          reasoning: res.reasoning,
          sources: res.sources,
          feedback: null,
          personalized: res.personalized,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry, I encountered an error: ${err instanceof Error ? err.message : "unknown error"}`,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div className="flex h-[480px] flex-col rounded-lg border border-border bg-card/30">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-4">
            <Bot className="h-8 w-8 text-muted-foreground/40" />
            <p className="text-center text-sm text-muted-foreground">
              Ask FinPilot anything about your finances.
              <br />
              Answers are tailored to your spending, budgets &amp; portfolio.
            </p>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 w-full max-w-sm">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-md border border-border/70 bg-secondary/60 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-border hover:text-foreground"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={`flex gap-2.5 ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {m.role === "assistant" && (
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-secondary">
                  <Bot className="h-3.5 w-3.5 text-muted-foreground" />
                </div>
              )}
              <div
                className={`max-w-[82%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-foreground"
                }`}
              >
                {/* Personalized badge — answer used the user's own financial data */}
                {m.role === "assistant" && m.personalized && (
                  <span className="mb-1.5 inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[9px] font-medium text-primary">
                    <Sparkles className="h-2.5 w-2.5" />
                    Personalized to your finances
                  </span>
                )}

                <p className="whitespace-pre-wrap">{m.content}</p>

                {/* Reasoning display */}
                {m.reasoning && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[10px] font-medium text-muted-foreground hover:text-foreground">
                      Why I said this
                    </summary>
                    <p className="mt-1 text-[11px] text-muted-foreground/80 leading-relaxed">
                      {m.reasoning}
                    </p>
                  </details>
                )}

                {/* Sources */}
                {m.sources && m.sources.length > 0 && (
                  <details className="mt-1.5">
                    <summary className="cursor-pointer text-[10px] font-medium text-muted-foreground hover:text-foreground">
                      {m.sources.length} sources
                    </summary>
                    <ul className="mt-1.5 space-y-1">
                      {m.sources.slice(0, 3).map((s) => (
                        <li key={s.id} className="rounded border border-border/50 p-1.5">
                          <p className="line-clamp-2 text-[11px] text-muted-foreground">
                            {s.content}
                          </p>
                          <span className="font-mono text-[9px] text-muted-foreground/60">
                            sim {(s.similarity * 100).toFixed(0)}%
                          </span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}

                {/* Thumbs up/down feedback for assistant messages */}
                {m.role === "assistant" && (
                  <div className="mt-2 flex items-center gap-1.5 border-t border-border/30 pt-1.5">
                    {m.feedback ? (
                      <span className="text-[10px] text-muted-foreground">
                        {m.feedback === "up" ? "Thanks!" : "Sorry about that."}
                      </span>
                    ) : (
                      <>
                        <span className="text-[10px] text-muted-foreground/60">Helpful?</span>
                        <button
                          onClick={() => void handleFeedback(i, true)}
                          className="rounded p-0.5 text-muted-foreground hover:text-emerald-500 transition-colors"
                          title="Thumbs up"
                        >
                          <ThumbsUp className="h-3 w-3" />
                        </button>
                        <button
                          onClick={() => void handleFeedback(i, false)}
                          className="rounded p-0.5 text-muted-foreground hover:text-red-500 transition-colors"
                          title="Thumbs down"
                        >
                          <ThumbsDown className="h-3 w-3" />
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
              {m.role === "user" && (
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-primary/10">
                  <User className="h-3.5 w-3.5 text-primary" />
                </div>
              )}
            </div>
          ))
        )}
        {loading && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <div className="flex h-6 w-6 items-center justify-center rounded-full border border-border bg-secondary">
              <Bot className="h-3.5 w-3.5" />
            </div>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span className="text-xs">Thinking…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send(input);
              }
            }}
            placeholder="Ask about your finances… (Enter to send)"
            rows={1}
            className="flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            style={{ minHeight: 36, maxHeight: 100 }}
          />
          <Button
            size="icon"
            onClick={() => void send(input)}
            disabled={!input.trim() || loading}
            className="shrink-0"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-1.5 text-[10px] text-muted-foreground/60">
          Not financial advice. Set ANTHROPIC_API_KEY for AI answers.
        </p>
      </div>
    </div>
  );
}
