import * as React from "react";
import { cn } from "@/lib/utils";

// shadcn/ui-style input on FinPilot tokens (8px radius, indigo focus ring).
export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-11 w-full rounded-md border border-input bg-background/60 px-3.5 py-2 text-sm",
        "ring-offset-background transition-colors duration-200 placeholder:text-muted-foreground/70",
        "focus-visible:border-primary/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";

export { Input };
