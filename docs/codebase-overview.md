# Codebase Overview

Snapshot of the `raumdeuterappv2` repo. Useful for onboarding and AI agents that need fast orientation. Last refreshed: 2026-05-04.

## Structure (pnpm monorepo)

```
raumdeuterappv2/
├── apps/
│   ├── web/          # Next.js frontend (active)
│   └── api/          # not yet implemented
├── packages/
│   └── shared-types/ # OpenAPI types & schemas
├── scripts/          # Python utilities
├── transformation/   # Data transformation scripts
├── utils/            # Utility modules
└── docs/             # Project docs (this file)
```

Package manager: `pnpm@10.33.2`. Root scripts: `dev`, `build`, `lint`, `typecheck`, `openapi:gen`.

## Frontend stack (`apps/web`)

- **Next.js 16.2.4** — App Router, server + client components, file-based routing under `src/app/`
- **React 19.2.4**
- **TypeScript** — strict mode, OpenAPI-generated types
- **Tailwind CSS 4** — `@theme` design tokens + `@utility` definitions in `src/app/globals.css`
- **TanStack React Query 5.100.5** — `staleTime: 5min`, `refetchOnWindowFocus: false`, `retry: 1`
- **openapi-fetch 0.17.0** — typed API client (`src/lib/api.ts`)
- **Zustand 5** — `useGlobalFilters` (`src/lib/store.ts`), `useSidebar` (`src/lib/sidebar-store.ts`, persisted)
- **Radix UI** — dialog, tabs, slider, tooltip, popover, label
- **lucide-react** — icons
- **class-variance-authority + clsx + tailwind-merge** — class composition
- No animation libraries (no framer-motion, react-spring) — only CSS transitions + Tailwind built-in `animate-pulse` / `animate-spin`

## Routes

```
/                                # dashboard
/scout/rankings                  # leaderboard with pagination
/scout/scatter                   # comparative metrics
/scout/screener                  # filter by criteria
/scout/bar                       # bar chart views
/scout/potential                 # age-cohort lanes (infinite scroll)
/scout/profile/[wyscoutId]       # individual player profile
/teams/best-xi                   # optimal lineup builder
/api/club-logo                   # image proxy
/api/player-image                # image proxy
```

## Design tokens (`src/app/globals.css`)

- Theme: dark only, `color-scheme: dark` enforced
- Surfaces: `--color-surface`, `--color-surface-{dim,low,mid,high,highest}`
- Primary: `--color-primary` `#14d1ff` (cyan)
- Secondary: `--color-secondary` `#00ff41` (green — positive trends)
- Tertiary: `--color-tertiary` `#ffd5ae` (orange)
- Error: `--color-error` `#ffb4ab`
- Radius scale: `--radius-sm` (0.125rem) → `--radius-xl` (0.75rem)
- Fonts: `--font-inter` (sans), `--font-space-grotesk` (mono)
- Custom utilities: `glass` (frosted blur), `glow-primary`, `label-caps`, `data-mono`

## Key files

| Path | Purpose |
|---|---|
| `src/app/layout.tsx` | Root layout — `QueryProvider`, `SeasonSync`, `Sidebar`, `TopBar` |
| `src/lib/query-provider.tsx` | React Query setup |
| `src/lib/api.ts` | Typed OpenAPI fetch client |
| `src/lib/store.ts` | Zustand global filter store |
| `src/lib/season-sync.tsx` | Auto-syncs season state to API availability |
| `src/components/ui/button.tsx` | CVA-based button |
| `src/components/ui/glass-card.tsx` | Frosted glass card with gradient overlay |
| `src/components/shell/sidebar.tsx` | Collapsible nav sidebar |
| `src/components/charts/age-cohort-lanes.tsx` | Infinite-scroll pagination + skeletons |

## Data fetching patterns

```ts
const q = useQuery({
  queryKey: ["resource", id, filters],
  queryFn: async () => {
    const { data, error } = await api.GET("/path", { params: { ... } });
    if (error) throw new Error(JSON.stringify(error));
    return data ?? defaultValue;
  },
  enabled: someCondition,
});
```

Pagination uses `useInfiniteQuery` (see `age-cohort-lanes.tsx`). Query keys follow `["resource", id, ...filters]` convention.

## State patterns

- Global filters (season, leagues, roles, age range, minutes min) live in Zustand
- Sidebar collapsed state persisted to localStorage
- URL search params used for pagination + page state, kept in sync via `router.push` / `router.replace`

## Loading / animation primitives

See `docs/superpowers/specs/` (or the loading-animations design doc) for the full system. TL;DR:

- Pulse skeletons + cyan shimmer sweep + top route-progress bar
- 200ms delay + 400ms min-hold via `useDelayedLoading` hook
- `loading.tsx` per route segment for first-paint
- `placeholderData: keepPreviousData` on filter-driven queries → silent refetches

## Conventions

- All client components annotated `"use client"` at top
- File names: kebab-case
- Components: `PascalCase.tsx`
- Hooks: `use-*.ts`
- Store files: `*-store.ts`
- Skeletons: `*-skeleton.tsx` under `src/components/skeletons/`
