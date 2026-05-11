import { Suspense } from "react";

import RankingsLoading from "./loading";
import { RankingsIndexClient } from "./rankings-index-client";

export default function RankingsPage() {
  return (
    <Suspense fallback={<RankingsLoading />}>
      <RankingsIndexClient />
    </Suspense>
  );
}
