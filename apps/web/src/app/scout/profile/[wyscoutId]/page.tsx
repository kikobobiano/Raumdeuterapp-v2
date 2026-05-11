import { Suspense } from "react";

import ProfileLoading from "./loading";
import { ProfileDetailClient } from "./profile-detail-client";

export default function ProfilePlayerPage() {
  return (
    <Suspense fallback={<ProfileLoading />}>
      <ProfileDetailClient />
    </Suspense>
  );
}
