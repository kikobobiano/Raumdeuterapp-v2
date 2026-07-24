import { Suspense } from "react";

import { DiscoverClient } from "./discover-client";

export default function DiscoverPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-on-surface-variant">Loading scouting…</div>}>
      <DiscoverClient />
    </Suspense>
  );
}
