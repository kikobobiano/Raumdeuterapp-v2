import { Suspense } from "react";

import RankingsLoading from "../rankings/loading";
import { ProfileLandingClient } from "./profile-landing-client";

export default function ProfileIndexPage() {
  return (
    <Suspense fallback={<RankingsLoading />}>
      <ProfileLandingClient />
    </Suspense>
  );
}
