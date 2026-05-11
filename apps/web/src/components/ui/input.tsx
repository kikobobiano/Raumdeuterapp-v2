import * as React from "react";

import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type = "text", ...props }, ref) => (
  <input
    ref={ref}
    type={type}
    className={cn(
      "flex h-10 w-full rounded-md bg-surface-low px-3 py-2 text-sm",
      "border border-transparent text-on-surface placeholder:text-on-surface-variant/60",
      "focus-visible:outline-none focus-visible:border-b-primary focus-visible:bg-surface-low",
      "transition-colors",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
