import Link from "next/link";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <GlassCard className="max-w-md w-full p-8 text-center space-y-4">
        <p className="text-5xl font-bold text-content-muted/30">404</p>
        <h2 className="text-lg font-semibold text-content">Page not found</h2>
        <p className="text-sm text-content-muted">
          This page does not exist or has been moved.
        </p>
        <Button asChild variant="ghost" size="sm">
          <Link href="/">Go home</Link>
        </Button>
      </GlassCard>
    </div>
  );
}
