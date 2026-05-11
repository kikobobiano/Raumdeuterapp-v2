import { Suspense } from "react";

import Loading from "./loading";
import { MinutesDistributionClient } from "./minutes-distribution-client";

export default function MinutesDistributionPage() {
  return (
    <Suspense fallback={<Loading />}>
      <MinutesDistributionClient />
    </Suspense>
  );
}
