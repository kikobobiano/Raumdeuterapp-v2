import { Suspense } from "react";

import { StandoutsClient } from "./standouts-client";

export default function StandoutsPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-on-surface-variant">Loading standouts…</div>}>
      <StandoutsClient />
    </Suspense>
  );
}
