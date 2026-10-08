import type { ReactNode } from "react";
import { cn } from "./utils";

export function ScrollArea({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn("overflow-y-auto", className)}>{children}</div>;
}
