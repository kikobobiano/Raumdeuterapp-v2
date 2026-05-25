import { Suspense } from "react";

import Loading from "./loading";
import { SquadValueClient } from "./squad-value-client";

export default function SquadValuePage() {
  return (
    <Suspense fallback={<Loading />}>
      <SquadValueClient />
    </Suspense>
  );
}
