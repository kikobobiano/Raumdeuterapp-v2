# xTV (expected transfer value) — design spec

**Status:** draft for implementation planning  
**Date:** 2026-05-11

## 1. Goal

Build an **xTV** model that learns from Transfermarkt (TM) realised transfers and Wyscout player-season stats, then populates a **single numeric column** on `data/players/all/*_all_leagues.parquet` rows.

User-facing interpretation: **expected transfer fee in €**, anchored to Transfermarkt market value at the same reference point, learned as a **premium/discount** over TM (not raw € alone).

## 2. Training label (approved)

- **Target:** \(y = \log(\text{fee}) - \log(\text{mv})\), with `fee` = `transfer_fee` and `mv` = TM market value at transfer date (`player_valuations` as-of last row ≤ `transfer_date`, or validated equivalent on the transfer row if consistent).
- **Filters:** `fee > 0`, `mv > 0`; exclude rows where fee is missing or non-paid semantics (loans without fee, etc.) per data audit.
- **Inference reconstruction:** \(\widehat{\text{xTV}} = \exp(\hat{y}) \cdot \text{mv}_{\text{align}}\) using the **same** `mv` definition as at inference time for parquet rows.

## 3. ID mapping TM ↔ Wyscout

1. **Primary:** `data/tm/people.csv` — `key_transfermarkt` ↔ `key_wyscout` (or `key_soccerway` if Wyscout id absent and pipeline already resolves via existing scripts).
2. **Fallback:** fuzzy / nearest name match against the correct **`players_<season>`** row set; unresolved ids logged to an **audit table** (tm_player_id, name, season, best candidate, score) for manual review.
3. **Reuse:** extend patterns from `scripts/build_player_valuations.py` and `scripts/enrich_with_tm.py`; avoid duplicate ad-hoc mapping logic.

## 4. Feature sets — two models

### 4.1 Wyscout snapshot (both models)

Always from **one parquet row** = one player-season (Wyscout league/club/minutes/indices for that season). Do not replace this with TM club for core performance features.

**Minimum agreed set:**

- Six game-area indices (`distribution_index`, `take_ons_index`, `assistance_index`, `finishing_index`, `aerial_play_index`, `ground_defense_index`).
- Age at season reference (DOB + season end or consistent app rule).
- Wyscout `league` (string as in parquets), `club`, `Minutes played`.
- \(\log(\text{mv})\) at aligned reference date (see §7).
- Position / role bucket if stable in pipeline (optional v1; same encoding both models).

### 4.2 Full model — transfer context (training / simulator only)

Additional columns from **`transfers.csv`**, joined to the Wyscout season row matched to that transfer:

| Feature | Source |
|--------|--------|
| `from_club_id`, `to_club_id` | `transfers` (prefer id; names for QA) |
| `from_league`, `to_league` | `data/tm/clubs.csv`: `club_id` → `domestic_competition_id` (TM codes, e.g. `L1`, `GB1`) |

**Caveat:** `clubs.csv` may reflect a **latest** club snapshot; historic `domestic_competition_id` can be wrong for old moves (promotion/relegation). **v1:** document bias; **v2:** time-aware club→league if data exists in scrape.

**Encoding:** high-cardinality clubs/leagues — target encoding or LOO within **temporal CV** to limit leakage; tree models with native categoricals acceptable with rare-level grouping.

### 4.3 Baseline model — parquet column (approved)

- **Same label** \(y = \log(\text{fee}) - \log(\text{mv})\).
- **Features:** §4.1 only (no `from_*` / `to_*`).
- **Purpose:** every `players_*` row has Wyscout + `mv`; no hypothetical buyer/seller needed.
- **Artifact:** baseline model + feature pipeline is what **writes** the new parquet column (name TBD, e.g. `x_tv_eur`).

### 4.4 Full model — artifact

Trained and versioned for **analysis / future UI** (“what if move from A→B”). **Does not** populate the default parquet column in v1 unless product asks later.

## 5. Season alignment

- Each training row: transfer `(player_tm_id, transfer_date, transfer_season)` → map to Wyscout id → pick `players_<YYYY>` where YYYY matches the **season of the player state** used (rule: map `transfer_season` to calendar season id consistent with parquet naming; document edge cases at window boundaries).

## 6. Train / validation

- **Split:** temporal — train on transfers before cutoff date; validate after (no random shuffle across time).
- **Metrics:** MAE on \(y\); Spearman on reconstructed € `xTV`; slice by league / fee decile.
- **Leakage checks:** features only from Wyscout season and TM fields known **at or before** transfer date; `mv` strictly as-of ≤ `transfer_date`.

## 7. Market value on parquet rows (inference)

- For each `(wyscout_id, season)` row: `mv` = last TM valuation ≤ **reference date** for that season (e.g. season end or fixed “as of” date used app-wide). Reuse valuation pipeline from `build_player_valuations` output or equivalent join.
- \(\widehat{\text{xTV}} = \exp(\hat{y}_{\text{baseline}}) \cdot \text{mv}\).

## 8. Outputs

1. **Training dataset** (optional persisted): transfer-level table with features + \(y\) + splits + audit flags.
2. **Model artifacts:** baseline (required); full (required for research, optional in API).
3. **Parquets:** new column on `*_all_leagues.parquet` from baseline; regeneration scripted (not hand-edited).
4. **Documentation:** mapping audit stats, row counts dropped, date of TM snapshot.

## 9. Out of scope (v1)

- Live TM scraping; API surface in FastAPI; UI for counterfactual A→B moves.
- Perfect historic league for every club-year (see §4.2).
- Joint model for zero-fee probability (optional later).

## 10. Spec self-review

- No unresolved “TBD” on approved choices: label B, Wyscout + transfer extras, baseline-only parquet, two-model split.
- **Explicit ambiguity resolved:** when Wyscout club ≠ TM `from_club`, both are allowed; model learns from realised moves without forcing equality.
- **Scope:** single implementation plan can cover data join + two trainings + parquet write; API/UI are separate slices.

---

**Next step:** implementation plan (`writing-plans` / `docs/superpowers/plans/`) after stakeholder sign-off on this file.
