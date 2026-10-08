import * as React from "react";
import { cn } from "./utils";

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(
        "flex min-h-20 w-full rounded-md border border-border bg-input-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      {...props}
    />
  );
}
