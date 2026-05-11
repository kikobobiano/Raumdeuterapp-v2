/** Wyscout team photos — proxied via Next to avoid hotlink issues */
const WYSCOUT_TEAM_IMG = /^https:\/\/cdn[0-9]*\.wyscout\.com\/photos\/team\//i;
const WYSCOUT_PLAYER_IMG = /^https:\/\/cdn[0-9]*\.wyscout\.com\/photos\/player\//i;
/** Public crop variants: ``g{id}_100x130.png``, ``g-{id}_100x130.png``, ``{id}_100x130.png``. */
const WYSCOUT_PLAYER_PUBLIC = /^https:\/\/cdn[0-9]*\.wyscout\.com\/photos\/players\/public\/(?:g-?)?\d+_100x130\.png$/i;
const TRANSFERMARKT_PLAYER_IMG =
  /^https:\/\/img\.a\.transfermarkt\.technology\/portrait\//i;

export function wyscoutClubLogoSrc(url: string): string {
  if (WYSCOUT_TEAM_IMG.test(url)) {
    return `/api/club-logo?url=${encodeURIComponent(url)}`;
  }
  return url;
}

export function wyscoutPlayerImageSrc(url: string): string {
  if (
    WYSCOUT_PLAYER_IMG.test(url) ||
    WYSCOUT_PLAYER_PUBLIC.test(url) ||
    TRANSFERMARKT_PLAYER_IMG.test(url)
  ) {
    return `/api/player-image?url=${encodeURIComponent(url)}`;
  }
  return url;
}
