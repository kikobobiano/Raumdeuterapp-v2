"use client";

import * as React from "react";

import { wyscoutClubLogoSrc } from "@/lib/wyscout-image";
import { cn } from "@/lib/utils";

export interface ClubLogoImgProps extends Omit<React.ComponentPropsWithoutRef<"img">, "src"> {
  /** HTTPS Wyscout team URL or proxied-compatible URL. */
  logoUrl: string | null | undefined;
}

/**
 * Crest only — no border, ring, or background (matches scout UI preference).
 */
export function ClubLogoImg({
  logoUrl,
  className = "h-7 w-7",
  alt = "",
  loading = "lazy",
  decoding = "async",
  ...rest
}: ClubLogoImgProps) {
  const [failed, setFailed] = React.useState(false);
  const [prevUrl, setPrevUrl] = React.useState(logoUrl);
  if (prevUrl !== logoUrl) {
    setPrevUrl(logoUrl);
    setFailed(false);
  }

  const trimmed = logoUrl?.trim();
  if (!trimmed || failed) {
    return <span className={cn("inline-block shrink-0", className)} aria-hidden />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={wyscoutClubLogoSrc(trimmed)}
      alt={alt}
      className={cn("shrink-0 object-contain", className)}
      loading={loading}
      decoding={decoding}
      onError={() => setFailed(true)}
      {...rest}
    />
  );
}
