"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <GlassCard className="max-w-md w-full p-8 text-center space-y-4">
        <h2 className="text-lg font-semibold text-content">Something went wrong</h2>
        <p className="text-sm text-content-muted">
          {error.digest ? `Error ID: ${error.digest}` : "An unexpected error occurred."}
        </p>
        <Button onClick={reset} variant="ghost" size="sm">
          Try again
        </Button>
      </GlassCard>
    </div>
  );
}
