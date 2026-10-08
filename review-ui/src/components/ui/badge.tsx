import { cn } from "./utils";

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: "default" | "secondary" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        variant === "secondary" && "border-transparent bg-secondary text-secondary-foreground",
        className,
      )}
      {...props}
    />
  );
}
